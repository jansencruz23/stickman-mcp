"""Opt-in checks that the real engines are installed. Run with: uv run pytest -m smoke"""

import struct
import wave
from pathlib import Path

import pytest

from stickman_mcp.config import load_channel_config
from stickman_mcp.images import SDXLLightningBackend
from stickman_mcp.tts import SAMPLE_RATE, KokoroEngine, clip_duration_seconds

SENTENCE = "Compound interest is the reason a small saving grows into a large one."
SCENE = "a stickman waving beside a giant coin"


@pytest.mark.smoke
def test_real_kokoro_speaks_the_channel_voice_into_a_24_khz_clip(tmp_path):
    destination = tmp_path / "smoke.wav"

    KokoroEngine().synthesize(SENTENCE, load_channel_config().voice, destination)

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


def png_size(path: Path) -> tuple[int, int]:
    """Reads the IHDR header directly, so the assertion does not lean on the imaging library."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    width, height = struct.unpack(">II", header[16:24])
    return width, height
