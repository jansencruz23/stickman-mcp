"""Opt-in checks that the real engines are installed. Run with: uv run pytest -m smoke"""

import wave

import pytest
from conftest import png_size

from stickman_mcp.config import load_channel_config
from stickman_mcp.images import SDXLLightningBackend
from stickman_mcp.tts import SAMPLE_RATE, KokoroEngine, clip_duration_seconds

SENTENCE = "Compound interest is the reason a small saving grows into a large one."
SCENE = "a stickman waving beside a giant coin"


@pytest.mark.smoke
def test_real_kokoro_speaks_the_channel_voice_into_a_24_khz_clip():
    """Writes into projects/smoke/ rather than a temp dir, because a human has to hear the locked voice."""
    config = load_channel_config()
    destination = config.projects_dir / "smoke" / f"kokoro-{config.voice}.wav"
    destination.parent.mkdir(parents=True, exist_ok=True)

    KokoroEngine().synthesize(SENTENCE, config.voice, config.voice_speed, destination)

    assert clip_duration_seconds(destination) > 0.5
    with wave.open(str(destination), "rb") as clip:
        assert clip.getframerate() == SAMPLE_RATE
        assert clip.getnchannels() == 1


@pytest.mark.smoke
def test_real_sdxl_lightning_draws_the_channel_style_at_the_configured_size():
    """Writes into projects/smoke/ rather than a temp dir, because a human has to look at it."""
    config = load_channel_config()
    destination = config.projects_dir / "smoke" / "sdxl-lightning.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    backend = SDXLLightningBackend(
        config.image_width, config.image_height, config.image_steps, config.guidance_scale
    )

    backend.generate(f"{config.style_prefix} {SCENE}", config.negative_prompt, 7, destination)

    assert png_size(destination) == (config.image_width, config.image_height)
