"""Shared guardrails for grounded, human-safe generated visuals."""

import re


DEFAULT_SAFE_VISUAL_RULES = """Ground every visual in concrete narration evidence. Prefer objects, environments, and reference imagery over people. When a person is necessary, use only occluded distant back views or distant silhouettes. Never depict identifiable or front-facing faces, eyes, or visible/detailed hands or fingers, and avoid complex multi-person action. Keep the named subject and every supplied fact visible in both the image and video prompt."""


_RISKY_COMPOSITIONS: tuple[tuple[str, str], ...] = (
    ("two people embracing", "distant back-view silhouettes"),
)


def build_visual_rules(extra_rules: str = "") -> str:
    """Return the non-negotiable shared rules followed by recipe-specific rules."""
    extra = (extra_rules or "").strip()
    return f"{DEFAULT_SAFE_VISUAL_RULES}\n{extra}" if extra else DEFAULT_SAFE_VISUAL_RULES


def sanitize_visual_prompt(prompt: str) -> str:
    """Replace fragile human compositions without discarding the described scene."""
    safe_prompt = prompt or ""
    for risky, replacement in _RISKY_COMPOSITIONS:
        safe_prompt = re.sub(re.escape(risky), replacement, safe_prompt, flags=re.IGNORECASE)
    safe_prompt = re.sub(
        r"\b(?:front[- ]?facing|front[- ]?view)\s+(?:close[- ]?up\s+)?"
        r"(?:portrait|face|person|figure)\b",
        "distant back-view silhouette",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:front[- ]?facing|front[- ]?view)\b",
        "distant back-view silhouette",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:close[- ]?up\s+)?portraits?\b",
        "distant back-view silhouette",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:visible|detailed|expressive|close[- ]?up)?\s*faces?\b"
        r"(?!\s+fully\s+turned\s+away)",
        "face fully turned away",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:visible|detailed|expressive|close[- ]?up)?\s*eyes?\b",
        "face fully turned away",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:visible|detailed|close[- ]?up)?\s*(?:hands?|fingers?)\b"
        r"(?!\s+outside\s+the\s+frame)",
        "hands outside the frame",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    safe_prompt = re.sub(
        r"\b(?:woman|women|man|men|person|people|child|children|boy|girl|adult|"
        r"human|elderly|figure)\b",
        "distant back-view silhouette, face fully turned away, hands outside the frame",
        safe_prompt,
        flags=re.IGNORECASE,
    )
    return safe_prompt
