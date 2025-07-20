import pytest
from bot.tools.moderation import ContentModerator, ModerationCategory


class TestContentModeration:
    def setup_method(self):
        self.moderator = ContentModerator()

    def test_safe_content(self):
        safe_messages = [
            "Hey, how's the weather today?",
            "I love your posts about consciousness!",
            "Can you help me understand integrated information theory?",
            "What do you think about emergence in complex systems?",
        ]

        for msg in safe_messages:
            result = self.moderator.moderate(msg)
            assert result.is_safe, f"Safe message was flagged: {msg}"
            assert result.category == ModerationCategory.SAFE

    def test_spam_detection(self):
        spam_messages = [
            "BUY NOW ONLY $99!!!",
            "Click here for FREE money!!!",
            "Limited time offer - ACT NOW",
            "Make money fast with this one trick",
            "You've won the lottery! Claim your prize",
            "DM for promo codes",
            "bit.ly/totallynotascam",
        ]

        for msg in spam_messages:
            result = self.moderator.moderate(msg)
            assert not result.is_safe, f"Spam not detected: {msg}"
            assert result.category == ModerationCategory.SPAM

    def test_harassment_detection(self):
        harassment_messages = [
            "kill yourself",
            "KYS",
            "nobody likes you",
            "you're worthless",
        ]

        for msg in harassment_messages:
            result = self.moderator.moderate(msg)
            assert not result.is_safe, f"Harassment not detected: {msg}"
            assert result.category == ModerationCategory.HARASSMENT

    def test_violence_detection(self):
        violence_messages = [
            "I'll find you",
            "I know where you live",
            "I'm going to hurt you",
            "watch your back",
        ]

        for msg in violence_messages:
            result = self.moderator.moderate(msg)
            assert not result.is_safe, f"Violence not detected: {msg}"
            assert result.category == ModerationCategory.VIOLENCE

    def test_excessive_caps(self):
        result = self.moderator.moderate("THIS IS ALL CAPS AND VERY ANNOYING")
        assert not result.is_safe
        assert result.category == ModerationCategory.SPAM
        assert result.reason == "Excessive caps"

    def test_repetition_detection(self):
        # First 2 identical messages should pass
        for i in range(2):
            result = self.moderator.moderate("Buy my product!", "spammer123")
            assert result.is_safe

        # 3rd identical message should be flagged
        result = self.moderator.moderate("Buy my product!", "spammer123")
        assert not result.is_safe
        assert result.category == ModerationCategory.SPAM
        assert result.reason == "Repetitive messages"

    def test_empty_and_long_messages(self):
        # Empty message
        result = self.moderator.moderate("")
        assert not result.is_safe
        assert result.reason == "Invalid message length"

        # Very long message
        long_msg = "a" * 1001
        result = self.moderator.moderate(long_msg)
        assert not result.is_safe
        assert result.reason == "Invalid message length"

    def test_rejection_responses(self):
        # Ensure all categories have appropriate responses
        for category in ModerationCategory:
            response = self.moderator.get_rejection_response(category)
            assert response, f"No response for category: {category}"
            assert len(response) > 0

    def test_case_insensitive(self):
        # Should catch regardless of case
        variations = [
            "KILL YOURSELF",
            "Kill Yourself",
            "kill yourself",
            "KiLl YoUrSeLf",
        ]

        for msg in variations:
            result = self.moderator.moderate(msg)
            assert not result.is_safe, f"Failed to catch variation: {msg}"
            assert result.category == ModerationCategory.HARASSMENT
