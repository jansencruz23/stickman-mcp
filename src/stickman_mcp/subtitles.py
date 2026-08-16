"""SRT cues mirroring the spoken Scenes: one cue per Scene, timed off the clips (ADR-0001)."""

from __future__ import annotations

from collections.abc import Sequence

from .script import Scene


def build_srt(scenes: Sequence[Scene], durations: Sequence[float], gap_seconds: float) -> str:
    """The gap falls after each Scene, so a cue starts exactly where its Narration Clip does."""
    blocks, start = [], 0.0
    for number, (scene, duration) in enumerate(zip(scenes, durations), start=1):
        blocks.append(f"{number}\n{_stamp(start)} --> {_stamp(start + duration)}\n{scene.narration}\n")
        start += duration + gap_seconds
    return "\n".join(blocks) + "\n" if blocks else ""


def _stamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{milliseconds:03d}"
