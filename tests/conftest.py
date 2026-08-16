import json
import math
import re
import struct
import subprocess
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
    """A real 16:9 PNG coloured from the seed, so two seeds can never produce the same bytes."""
    colour = (seed % 256, seed // 256 % 256, seed // 65536 % 256)
    write_solid_png(destination, 16, 9, colour)


def write_solid_png(destination: Path, width: int, height: int, colour: tuple[int, int, int]) -> None:
    """One flat colour at any size, so a test can hand ffmpeg an aspect ratio of its choosing."""
    raw = (b"\x00" + bytes(colour) * width) * height
    destination.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
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


def write_tone_wav(destination: Path, seconds: float, hertz: float = 440.0) -> None:
    """A full-scale sine, so a mixed-in copy's measured level reads straight as the applied gain."""
    frames = round(seconds * SAMPLE_RATE)
    samples = (round(32767 * math.sin(math.tau * hertz * frame / SAMPLE_RATE)) for frame in range(frames))
    with wave.open(str(destination), "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(SAMPLE_RATE)
        clip.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def probe(path: Path) -> dict:
    """Everything the render criteria assert about the output is read back with ffprobe, not ffmpeg."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(json.loads(result.stdout))


def probe_seconds(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def stream(path: Path, kind: str) -> dict:
    return next(found for found in probe(path)["streams"] if found["codec_type"] == kind)


def first_frame(path: Path) -> bytes:
    """Raw RGB of the opening frame, so a test can look at what a viewer would actually see."""
    return first_frame_at(path, 0.0)


def first_frame_at(path: Path, seconds: float) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{seconds:.6f}", "-i", str(path)]
        + ["-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    )
    return result.stdout


def peak_dbfs(path: Path, from_seconds: float = 0.0) -> float:
    """Full scale is 0 dB, so a bed mixed under silence peaks at exactly the gain it was given."""
    result = subprocess.run(
        ["ffmpeg", "-v", "info", "-ss", str(from_seconds), "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    found = re.search(r"max_volume: (-?\d+(?:\.\d+)?) dB", result.stderr)
    assert found, f"ffmpeg reported no peak level for {path.name}"
    return float(found.group(1))


def pixel(frame: bytes, x: int, y: int, width: int = 1920) -> tuple[int, int, int]:
    start = (y * width + x) * 3
    return frame[start], frame[start + 1], frame[start + 2]


def frame_colours(path: Path) -> list[tuple[int, int, int]]:
    """Every frame flattened to one pixel, so a test can name the exact frame a cut lands on."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path)]
        + ["-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    )
    raw = result.stdout
    return [(raw[at], raw[at + 1], raw[at + 2]) for at in range(0, len(raw) - 2, 3)]
