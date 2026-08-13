"""Batch narration: one Narration Clip per Scene, resumable because finished clips are skipped."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .runs import RunStore
from .script import Script
from .tts import TTSEngine, TTSError, clip_duration_seconds


@dataclass(frozen=True)
class NarrationClip:
    scene_id: int
    duration_seconds: float
    synthesized: bool


def synthesize(runs: RunStore, run_id: str, script: Script, engine: TTSEngine, voice: str) -> list[NarrationClip]:
    """Durations always come from the files on disk, so skipped Scenes report the same as fresh ones."""
    clips = []
    for scene in script.scenes:
        destination = runs.narration_clip_path(run_id, scene.id)
        missing = not destination.is_file()
        if missing:
            _synthesize_to(destination, scene.narration, engine, voice)
        clips.append(NarrationClip(scene.id, clip_duration_seconds(destination), missing))
    return clips


def _synthesize_to(destination: Path, narration: str, engine: TTSEngine, voice: str) -> None:
    """Publish by rename, so an interrupted clip is never mistaken for a finished one on resume."""
    partial = destination.with_name(destination.name + ".part")
    try:
        engine.synthesize(narration, voice, partial)
    except TTSError:
        raise
    except Exception as exc:
        raise TTSError(
            f"the speech engine failed on {destination.name}: {exc}. Check the espeak-ng and "
            "model setup in the README, then call stickman_synthesize_narration again."
        ) from None
    partial.replace(destination)
