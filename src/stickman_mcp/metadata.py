"""Upload metadata: the fields the creator pastes into YouTube, and the disclosure they must carry."""

from __future__ import annotations

from collections.abc import Sequence

# Part of the description, not a section of its own, so what gets pasted is already compliant.
DISCLOSURE = "Narration and images in this video were generated with AI."


def build_metadata(title: str, description: str, tags: Sequence[str]) -> str:
    """One section per upload field, so the creator pastes each straight into YouTube."""
    return f"TITLE\n{title}\n\nDESCRIPTION\n{description}\n\n{DISCLOSURE}\n\nTAGS\n{', '.join(tags)}\n"
