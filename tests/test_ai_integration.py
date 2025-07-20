#!/usr/bin/env python
"""Test AI integration without posting to Bluesky"""

import asyncio

from bot.response_generator import ResponseGenerator
from bot.config import settings


async def test_response_generator():
    """Test the response generator with various inputs"""
    print("🧪 Testing AI Integration")
    print(f"   Bot name: {settings.bot_name}")
    print(f"   AI enabled: {'Yes' if settings.anthropic_api_key else 'No'}")
    print()
    
    # Create response generator
    generator = ResponseGenerator()
    
    # Test cases
    test_cases = [
        {
            "mention": f"@{settings.bot_name} What's your favorite color?",
            "author": "test.user",
            "description": "Simple question"
        },
        {
            "mention": f"@{settings.bot_name} Can you help me understand integrated information theory?",
            "author": "curious.scientist",
            "description": "Complex topic"
        },
        {
            "mention": f"@{settings.bot_name} hello!",
            "author": "friendly.person",
            "description": "Simple greeting"
        },
        {
            "mention": f"@{settings.bot_name} What do you think about consciousness?",
            "author": "philosopher",
            "description": "Philosophical question"
        }
    ]
    
    # Run tests
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['description']}")
        print(f"  From: @{test['author']}")
        print(f"  Raw text: {test['mention']}")
        
        # In real AT Protocol, mentions are facets with structured data
        # For testing, we pass the full text (bot can parse if needed)
        print(f"  (Note: In production, @{settings.bot_name} would be a structured mention)")
        
        try:
            response = await generator.generate(
                mention_text=test['mention'],
                author_handle=test['author'],
                thread_context=""
            )
            print(f"  Response: {response}")
            print(f"  Length: {len(response)} chars")
            
            # Verify response is within Bluesky limit
            if len(response) > 300:
                print("  ⚠️  WARNING: Response exceeds 300 character limit!")
            else:
                print("  ✅ Response within limit")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    # Test response consistency
    if generator.agent:
        print("🔄 Testing response consistency...")
        test_mention = f"@{settings.bot_name} What are you?"
        responses = []
        
        for i in range(3):
            response = await generator.generate(
                mention_text=test_mention,
                author_handle="consistency.tester",
                thread_context=""
            )
            responses.append(response)
            print(f"  Response {i+1}: {response[:50]}...")
        
        # Check if responses are different (they should be somewhat varied)
        if len(set(responses)) == 1:
            print("  ⚠️  All responses are identical - might want more variation")
        else:
            print("  ✅ Responses show variation")
    
    print("\n✨ Test complete!")


async def test_direct_agent():
    """Test the Anthropic agent directly"""
    if not settings.anthropic_api_key:
        print("⚠️  No Anthropic API key found - skipping direct agent test")
        return
    
    print("\n🤖 Testing Anthropic Agent Directly")
    
    try:
        from bot.agents.anthropic_agent import AnthropicAgent
        agent = AnthropicAgent()
        
        # Test a simple response
        response = await agent.generate_response(
            mention_text=f"@{settings.bot_name} explain your name",
            author_handle="name.curious",
            thread_context=""
        )
        
        print(f"Direct agent response: {response}")
        print(f"Response length: {len(response)} chars")
        
    except Exception as e:
        print(f"❌ Direct agent test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print(f"{settings.bot_name} Bot - AI Integration Test")
    print("=" * 60)
    
    asyncio.run(test_response_generator())
    asyncio.run(test_direct_agent())