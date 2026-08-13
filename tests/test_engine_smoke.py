"""Opt-in checks that the real engines are installed. Run with: uv run pytest -m smoke"""

import wave

import pytest

from stickman_mcp.config import load_channel_config
from stickman_mcp.tts import SAMPLE_RATE, KokoroEngine, clip_duration_seconds

SENTENCE = "Compound interest is the reason a small saving grows into a large one."


@pytest.mark.smoke
def test_real_kokoro_speaks_the_channel_voice_into_a_24_khz_clip(tmp_path):
    destination = tmp_path / "smoke.wav"

    KokoroEngine().synthesize(SENTENCE, load_channel_config().voice, destination)

    assert clip_duration_seconds(destination) > 0.5
    with wave.open(str(destination), "rb") as clip:
        assert clip.getframerate() == SAMPLE_RATE
        assert clip.getnchannels() == 1
