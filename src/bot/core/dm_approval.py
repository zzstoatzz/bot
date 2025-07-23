"""Event-driven approval system for operator interactions"""

import json
import logging
import os
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent

from bot.config import settings
from bot.database import thread_db

logger = logging.getLogger("bot.approval")

# Simplified permission levels - just what we need
ApprovalRequired = Literal["operator_only", "guided", "free"]

# Which parts of personality need what approval
PERSONALITY_PERMISSIONS = {
    "interests": "free",              # Can add freely
    "current_state": "free",          # Self-reflection updates
    "communication_style": "guided",  # Within character bounds
    "core_identity": "operator_only", # Needs approval
    "boundaries": "operator_only",    # Safety critical
}

OPERATOR_HANDLE = "alternatebuild.dev"


class ApprovalDecision(BaseModel):
    """Structured output for approval interpretation"""
    approved: bool
    confidence: Literal["high", "medium", "low"]
    interpretation: str  # Brief explanation of why this decision was made


def create_approval_request(request_type: str, request_data: dict, thread_uri: str | None = None) -> int:
    """Create a new approval request in the database
    
    Args:
        request_type: Type of approval request
        request_data: Data for the request
        thread_uri: Optional thread URI to notify after approval
    
    Returns the approval request ID
    """
    try:
        # Add metadata to the request
        request_data["operator_handle"] = OPERATOR_HANDLE
        
        approval_id = thread_db.create_approval_request(
            request_type=request_type,
            request_data=json.dumps(request_data),
            thread_uri=thread_uri
        )
        
        logger.info(f"Created approval request #{approval_id} for {request_type}")
        return approval_id
        
    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        return 0


def check_pending_approvals(include_notified: bool = True) -> list[dict]:
    """Get all pending approval requests"""
    return thread_db.get_pending_approvals(include_notified=include_notified)


async def process_dm_for_approval(dm_text: str, sender_handle: str, message_timestamp: str, notification_timestamp: str | None = None) -> list[int]:
    """Use an agent to interpret if a DM contains approval/denial
    
    Args:
        dm_text: The message text
        sender_handle: Who sent the message
        message_timestamp: When this message was sent
        notification_timestamp: When we notified about pending approvals (if known)
    
    Returns list of approval IDs that were processed
    """
    if sender_handle != OPERATOR_HANDLE:
        return []
    
    processed = []
    pending = check_pending_approvals()
    
    if not pending:
        return []
    
    # Only process if this message is recent (within last 5 minutes of a pending approval)
    # This helps avoid processing old messages
    from datetime import datetime, timedelta, timezone
    try:
        # Parse the message timestamp (from API, has timezone)
        msg_time = datetime.fromisoformat(message_timestamp.replace('Z', '+00:00'))
        
        # Check if this message could be a response to any pending approval
        relevant_approval = None
        for approval in pending:
            # Parse approval timestamp (from DB, no timezone - assume UTC)
            approval_time_str = approval["created_at"]
            # SQLite returns timestamps in format like "2025-07-23 02:29:42"
            if ' ' in approval_time_str:
                approval_time = datetime.strptime(approval_time_str, "%Y-%m-%d %H:%M:%S")
                approval_time = approval_time.replace(tzinfo=timezone.utc)
            else:
                approval_time = datetime.fromisoformat(approval_time_str).replace(tzinfo=timezone.utc)
            
            if msg_time > approval_time and (msg_time - approval_time) < timedelta(minutes=5):
                relevant_approval = approval
                break
        
        if not relevant_approval:
            # Message is too old to be an approval response
            return []
    except Exception as e:
        logger.warning(f"Could not parse timestamps: {e}")
        # Continue anyway if we can't parse timestamps
        # But use the LAST pending approval, not the first
        relevant_approval = pending[-1] if pending else None
    
    # Set up API key for the agent
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    
    # Create a dedicated agent for approval interpretation
    approval_agent = Agent(
        "anthropic:claude-3-5-haiku-latest",
        system_prompt="You are interpreting whether a message from the bot operator constitutes approval or denial of a request. Be generous in interpretation - if they seem positive, it's likely approval.",
        output_type=ApprovalDecision
    )
    
    # Process only the relevant approval
    if relevant_approval:
        approval_id = relevant_approval["id"]
        request_data = json.loads(relevant_approval["request_data"])
        
        # Build context for the agent
        prompt = f"""An approval was requested for:

Type: {relevant_approval['request_type']}
Description: {request_data.get('description', 'No description')}
Details: {json.dumps(request_data, indent=2)}

The operator responded: "{dm_text}"

Interpret whether this response approves or denies the request."""
        
        # Get structured interpretation
        result = await approval_agent.run(prompt)
        decision = result.output
        
        # Only process high/medium confidence decisions
        if decision.confidence in ["high", "medium"]:
            thread_db.resolve_approval(approval_id, decision.approved, dm_text)
            processed.append(approval_id)
            status = "approved" if decision.approved else "denied"
            logger.info(f"Request #{approval_id} {status} ({decision.confidence} confidence): {decision.interpretation}")
        else:
            # Low confidence interpretation - skip
            pass
    
    return processed


async def notify_operator_of_pending(client, notified_ids: set | None = None):
    """Send a DM listing pending approvals (called periodically)
    
    Args:
        client: The bot client
        notified_ids: Set of approval IDs we've already notified about
    """
    # Get only unnotified pending approvals
    new_pending = check_pending_approvals(include_notified=False)
    if not new_pending:
        return  # Nothing new to notify about
    
    try:
        chat_client = client.client.with_bsky_chat_proxy()
        convos = chat_client.chat.bsky.convo.list_convos()
        
        operator_convo = None
        for convo in convos.convos:
            if any(member.handle == OPERATOR_HANDLE for member in convo.members):
                operator_convo = convo
                break
        
        if operator_convo:
            # Format pending approvals
            lines = ["📋 Pending approvals:"]
            for approval in new_pending:
                data = json.loads(approval["request_data"])
                lines.append(f"\n#{approval['id']} - {approval['request_type']}")
                lines.append(f"   {data.get('description', 'No description')}")
            
            lines.append("\nReply to approve or deny.")
            
            chat_client.chat.bsky.convo.send_message(
                data={
                    "convoId": operator_convo.id,
                    "message": {
                        "text": "\n".join(lines),
                        "facets": []
                    }
                }
            )
            
            logger.info(f"Notified operator about {len(new_pending)} new approvals")
            
    except Exception as e:
        logger.error(f"Failed to notify operator: {e}")


def needs_approval(section: str, change_type: str = "edit") -> bool:
    """Check if a personality change needs operator approval"""
    permission = PERSONALITY_PERMISSIONS.get(section, "operator_only")
    
    if permission == "operator_only":
        return True
    elif permission == "guided" and change_type == "major":
        return True
    else:
        return False