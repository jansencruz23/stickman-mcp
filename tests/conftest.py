import json
import struct
import threading
import time
import wave
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from stickman_mcp import server
from stickman_mcp.config import CONFIG_ENV_VAR, load_channel_config
from stickman_mcp.tts import SAMPLE_RATE

TEST_CHANNEL = """
[paths]
projects_dir = "projects"
music_dir = "music"

[style]
prefix = "test stickman style,"
negative_prompt = "photo"

[image]
base_seed = 4242
"""

DEFAULT_CLIP_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _isolated_config_cache():
    server.channel_config.cache_clear()
    server.image_backend.cache_clear()
    yield
    server.channel_config.cache_clear()
    server.image_backend.cache_clear()


@pytest.fixture
def channel(tmp_path, monkeypatch):
    """Point the tools at a throwaway channel config and projects folder."""
    source = tmp_path / "channel.toml"
    source.write_text(TEST_CHANNEL, encoding="utf-8")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(source))
    return load_channel_config(source)


class FakeTTS:
    """Writes silent clips of a duration the test chose, and logs every call it receives."""

    def __init__(self) -> None:
        self.seconds: dict[str, float] = {}
        self.calls: list[tuple[str, str, Path]] = []

    def synthesize(self, text: str, voice: str, destination: Path) -> None:
        self.calls.append((text, voice, destination))
        write_silent_wav(destination, self.seconds.get(text, DEFAULT_CLIP_SECONDS))


def write_silent_wav(destination: Path, seconds: float) -> None:
    """Built with stdlib wave, not the production writer, so durations stay an independent check."""
    with wave.open(str(destination), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(SAMPLE_RATE)
        clip.writeframes(b"\x00\x00" * round(seconds * SAMPLE_RATE))


@pytest.fixture
def fake_tts(monkeypatch):
    """Swap the real engine out at the tool surface; tests set per-narration durations on it."""
    engine = FakeTTS()
    monkeypatch.setattr(server, "tts_engine", lambda: engine)
    return engine


BACKEND_FAILURE = "CUDA out of memory"
GATE_TIMEOUT = 10.0


@dataclass(frozen=True)
class ImageCall:
    prompt: str
    negative_prompt: str
    seed: int
    destination: Path


class FakeImages:
    """Writes tiny PNGs whose bytes follow the seed, and logs every prompt and seed it is given."""

    def __init__(self) -> None:
        self.calls: list[ImageCall] = []
        self.fail_after: int | None = None
        self.pace: threading.Semaphore | None = None

    def generate(self, prompt: str, negative_prompt: str, seed: int, destination: Path) -> None:
        if self.pace is not None:
            assert self.pace.acquire(timeout=GATE_TIMEOUT), "the test never released this image"
        self.calls.append(ImageCall(prompt, negative_prompt, seed, destination))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise RuntimeError(BACKEND_FAILURE)
        write_tiny_png(destination, seed)


def write_tiny_png(destination: Path, seed: int) -> None:
    """A real 1x1 PNG coloured from the seed, so two seeds can never produce the same bytes."""
    pixel = bytes([0, seed % 256, seed // 256 % 256, seed // 65536 % 256])
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    destination.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(pixel))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


@pytest.fixture
def fake_images(monkeypatch):
    """Swap the real backend out at the tool surface; tests read its call log back."""
    backend = FakeImages()
    monkeypatch.setattr(server, "image_backend", lambda: backend)
    return backend


def poll_job(run_id: str, until: Callable[[dict], bool], timeout: float = GATE_TIMEOUT) -> dict:
    """Polls exactly as a caller would, so the test proves the polling contract, not internals."""
    deadline = time.monotonic() + timeout
    while True:
        status = json.loads(server.stickman_job_status(run_id))
        if until(status):
            return status
        assert time.monotonic() < deadline, f"job never reached the expected state: {status}"
        time.sleep(0.01)


def finished(status: dict) -> bool:
    return status["state"] != "running"
