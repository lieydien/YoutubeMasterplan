"""YouTube packaging helpers adapted from youtube-agent-skill (MIT).

https://github.com/Jakeschincariol/youtube-agent-skill
"""

from app.services.youtube_kit.hookscore import extract_hook, is_supported_text, score_hook
from app.services.youtube_kit.prompts import HOOK_FIRST_SCRIPT_SYSTEM_PROMPT
from app.services.youtube_kit.title_lint import lint_title

__all__ = [
    "HOOK_FIRST_SCRIPT_SYSTEM_PROMPT",
    "extract_hook",
    "is_supported_text",
    "lint_title",
    "score_hook",
]
