"""Logging configuration for the bot"""

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "critical": "bold red on white",
        "debug": "dim white",
        "http": "dim blue",
        "bot": "green",
        "mention": "bold magenta",
    }
)

console = Console(theme=custom_theme)


def setup_logging(debug: bool = False) -> None:
    """Set up logging with Rich"""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = RichHandler(
        console=console,
        show_time=False,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=debug,
    )

    if debug:
        handler.setLevel(logging.DEBUG)
        format_str = "[dim]{asctime}[/dim] {message}"
    else:
        handler.setLevel(logging.INFO)
        format_str = "{message}"

    formatter = logging.Formatter(format_str, style="{", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
