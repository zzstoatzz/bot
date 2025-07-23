"""Simple personality editing functions"""

import logging
from datetime import datetime

from bot.core.dm_approval import needs_approval
from bot.memory import MemoryType, NamespaceMemory

logger = logging.getLogger("bot.personality")


async def add_interest(memory: NamespaceMemory, interest: str, reason: str) -> bool:
    """Add a new interest - freely allowed"""
    try:
        # Get current interests
        current = await memory.get_core_memories()
        interests_mem = next(
            (m for m in current if m.metadata.get("label") == "interests"), None
        )

        if interests_mem:
            new_content = f"{interests_mem.content}\n- {interest}"
        else:
            new_content = f"## interests\n\n- {interest}"

        # Store updated interests
        await memory.store_core_memory("interests", new_content, MemoryType.PERSONALITY)

        # Log the change
        await memory.store_core_memory(
            "evolution_log",
            f"[{datetime.now().isoformat()}] Added interest: {interest} (Reason: {reason})",
            MemoryType.SYSTEM,
        )

        logger.info(f"Added interest: {interest}")
        return True

    except Exception as e:
        logger.error(f"Failed to add interest: {e}")
        return False


async def update_current_state(memory: NamespaceMemory, reflection: str) -> bool:
    """Update self-reflection - freely allowed"""
    try:
        # Just store the reflection, no formatting or headers
        await memory.store_core_memory(
            "current_state", reflection, MemoryType.PERSONALITY
        )

        logger.info("Updated current state")
        return True

    except Exception as e:
        logger.error(f"Failed to update state: {e}")
        return False


# Note: propose_style_change was removed because the validation logic was broken.
# Style changes should be handled through the approval system like other guided changes.


def request_operator_approval(
    section: str, change: str, reason: str, thread_uri: str | None = None
) -> int:
    """Request approval for operator-only changes

    Args:
        section: Personality section to change
        change: The proposed change
        reason: Why this change is needed
        thread_uri: Optional thread URI to notify after approval

    Returns approval request ID (0 if no approval needed)
    """
    if not needs_approval(section):
        return 0

    from bot.core.dm_approval import create_approval_request

    return create_approval_request(
        request_type="personality_change",
        request_data={
            "section": section,
            "change": change,
            "reason": reason,
            "description": f"Change {section}: {change[:50]}...",
        },
        thread_uri=thread_uri,
    )


async def process_approved_changes(memory: NamespaceMemory) -> int:
    """Process any approved personality changes

    Returns number of changes processed
    """
    import json

    from bot.database import thread_db

    processed = 0
    # Get recently approved personality changes that haven't been applied yet
    with thread_db._get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM approval_requests 
            WHERE request_type = 'personality_change' 
            AND status = 'approved'
            AND applied_at IS NULL
            ORDER BY resolved_at DESC
            """
        )
        approvals = [dict(row) for row in cursor.fetchall()]

    for approval in approvals:
        try:
            data = json.loads(approval["request_data"])
            section = data["section"]
            change = data["change"]

            # Apply the personality change
            if section in ["core_identity", "boundaries", "communication_style"]:
                # Apply the approved change
                await memory.store_core_memory(section, change, MemoryType.PERSONALITY)

                # Log the change with appropriate description
                log_entry = f"[{datetime.now().isoformat()}] "
                if section == "communication_style":
                    log_entry += f"Applied guided evolution to {section}"
                else:
                    log_entry += f"Operator approved change to {section}"
                
                await memory.store_core_memory(
                    "evolution_log",
                    log_entry,
                    MemoryType.SYSTEM,
                )

                processed += 1
                logger.info(f"Applied approved change to {section}")

                # Mark as applied
                with thread_db._get_connection() as conn:
                    conn.execute(
                        "UPDATE approval_requests SET applied_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (approval["id"],),
                    )

        except Exception as e:
            logger.error(f"Failed to process approval #{approval['id']}: {e}")

    return processed
