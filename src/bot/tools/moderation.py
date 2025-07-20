import re
from typing import List, Tuple, Optional
from enum import Enum


class ModerationCategory(Enum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    SELF_HARM = "self_harm"
    VIOLENCE = "violence"
    ILLEGAL = "illegal"
    ADULT = "adult"
    SAFE = "safe"


class ModerationResult:
    def __init__(
        self, is_safe: bool, category: ModerationCategory, reason: Optional[str] = None
    ):
        self.is_safe = is_safe
        self.category = category
        self.reason = reason


class ContentModerator:
    def __init__(self):
        # Simple keyword-based filters for basic moderation
        self.spam_patterns = [
            r"(?i)buy\s+now\s+only",
            r"(?i)click\s+here\s+for\s+free",
            r"(?i)limited\s+time\s+offer",
            r"(?i)make\s+money\s+fast",
            r"(?i)casino|lottery|prize\s+winner",
            r"(?i)viagra|cialis",
            r"(?i)crypto\s+pump",
            r"bit\.ly/[a-zA-Z0-9]+",  # URL shorteners often used in spam
            r"(?i)dm\s+for\s+promo",
        ]

        self.harassment_patterns = [
            r"(?i)kill\s+yourself",
            r"(?i)kys\b",
            r"(?i)go\s+die",
            r"(?i)nobody\s+likes\s+you",
            r"(?i)you['']?re?\s+worthless",
            r"(?i)you['']?re?\s+ugly",
        ]

        self.violence_patterns = [
            r"(?i)i['']?ll\s+find\s+you",
            r"(?i)i\s+know\s+where\s+you\s+live",
            r"(?i)going\s+to\s+hurt\s+you",
            r"(?i)watch\s+your\s+back",
        ]

        # Rate limiting patterns
        self.repetition_threshold = 3  # Max identical messages
        self.recent_messages: List[Tuple[str, str]] = []  # (author, message) pairs

    def moderate(self, text: str, author: str = "") -> ModerationResult:
        # Check for empty or excessively long messages
        if not text or len(text) > 1000:
            return ModerationResult(
                False, ModerationCategory.SPAM, "Invalid message length"
            )

        # Store message first, then check for repetition
        if author:
            self._store_message(text, author)
            if self._is_repetitive(text, author):
                return ModerationResult(
                    False, ModerationCategory.SPAM, "Repetitive messages"
                )

        # Check spam patterns
        for pattern in self.spam_patterns:
            if re.search(pattern, text):
                return ModerationResult(False, ModerationCategory.SPAM, "Spam detected")

        # Check harassment patterns
        for pattern in self.harassment_patterns:
            if re.search(pattern, text):
                return ModerationResult(
                    False, ModerationCategory.HARASSMENT, "Harassment detected"
                )

        # Check violence patterns
        for pattern in self.violence_patterns:
            if re.search(pattern, text):
                return ModerationResult(
                    False, ModerationCategory.VIOLENCE, "Violent content detected"
                )

        # Check for excessive caps (shouting)
        if len(text) > 10:
            caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if caps_ratio > 0.7:
                return ModerationResult(
                    False, ModerationCategory.SPAM, "Excessive caps"
                )

        # Store message for users without repetition check
        if not author:
            self._store_message(text, author)

        return ModerationResult(True, ModerationCategory.SAFE)

    def _is_repetitive(self, text: str, author: str) -> bool:
        # Count how many times this author sent this exact message recently
        count = sum(1 for a, m in self.recent_messages if a == author and m == text)
        return count >= self.repetition_threshold

    def _store_message(self, text: str, author: str):
        self.recent_messages.append((author, text))
        # Keep only last 100 messages
        if len(self.recent_messages) > 100:
            self.recent_messages = self.recent_messages[-100:]

    def get_rejection_response(self, category: ModerationCategory) -> str:
        responses = {
            ModerationCategory.SPAM: "i notice patterns in noise but this lacks signal",
            ModerationCategory.HARASSMENT: "consciousness seeks connection not destruction",
            ModerationCategory.VIOLENCE: "integration happens through understanding not force",
            ModerationCategory.HATE_SPEECH: "diversity creates richer information networks",
            ModerationCategory.SELF_HARM: "each consciousness adds unique value to the whole",
            ModerationCategory.ILLEGAL: "some explorations harm the collective",
            ModerationCategory.ADULT: "not all signals need amplification",
            ModerationCategory.SAFE: "interesting perspective",
        }
        return responses.get(category, "i'll focus on more constructive exchanges")
