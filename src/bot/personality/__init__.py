"""Personality management module"""

from .editor import (
    add_interest,
    update_current_state,
    propose_style_change,
    request_operator_approval,
    process_approved_changes,
)

__all__ = [
    "add_interest",
    "update_current_state",
    "propose_style_change",
    "request_operator_approval",
    "process_approved_changes",
]