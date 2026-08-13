"""Speech synthesis behind one swappable engine. A clip's length is its Scene's duration (ADR-0001)."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any, Protocol

import numpy as np

SAMPLE_RATE = 24000
LANG_CODE = "a"


class TTSError(Exception):
    """The speech engine could not produce a usable Narration Clip."""


class TTSEngine(Protocol):
    def synthesize(self, text: str, voice: str, destination: Path) -> None:
        """Write text, spoken in voice, to destination as a mono WAV."""


def clip_duration_seconds(path: Path) -> float:
    """Read a Scene's duration off its clip; nothing here ever transcribes audio (ADR-0001)."""
    try:
        with wave.open(str(path), "rb") as clip:
            return clip.getnframes() / clip.getframerate()
    except (OSError, wave.Error) as exc:
        raise TTSError(
            f"{path.name} is not a readable WAV clip: {exc}. Delete it and call "
            "stickman_synthesize_narration again to re-speak that Scene."
        ) from None


class KokoroEngine:
    """Kokoro-82M. The model loads on first synthesis, so importing this costs nothing."""

    def __init__(self) -> None:
        self._pipeline: Any = None

    def synthesize(self, text: str, voice: str, destination: Path) -> None:
        chunks = [result.audio for result in self._loaded()(text, voice=voice) if result.audio is not None]
        if not chunks:
            raise TTSError(f"Kokoro produced no audio for {text!r}. Check the voice name in channel.toml.")
        samples = np.concatenate([np.asarray(chunk, dtype=np.float32) for chunk in chunks])
        _write_wav(destination, samples)

    def _loaded(self) -> Any:
        if self._pipeline is None:
            from kokoro import KPipeline

            self._pipeline = KPipeline(lang_code=LANG_CODE)
        return self._pipeline


def _write_wav(destination: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(destination), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(SAMPLE_RATE)
        clip.writeframes(pcm.tobytes())
