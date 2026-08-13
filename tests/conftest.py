import wave
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
"""

DEFAULT_CLIP_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _isolated_config_cache():
    server.channel_config.cache_clear()
    yield
    server.channel_config.cache_clear()


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
