"""Opt-in: the real meta.ai, in the creator's own logged-in browser profile.

Excluded by default because it opens a browser, uses the account, and needs the one-time manual
login done first (scripts/meta_login.py).

    uv run pytest -m live
"""

import pytest
from conftest import png_size

from stickman_mcp import server
from stickman_mcp.meta_ai import MetaAIBackend

pytestmark = pytest.mark.live

SCENE = "a stickman waving beside a giant coin"


@pytest.fixture
def live_backend():
    """Built the way the server builds it, so this fails if the wiring drifts from the shipped config."""
    config = server.channel_config()
    backend = server.image_backend()
    if not isinstance(backend, MetaAIBackend):
        pytest.skip(f"channel.toml draws with {config.image_backend}, so there is no live Meta run to make")
    yield config, backend
    backend.close()


def test_real_meta_ai_answers_the_channel_style_with_a_picture(live_backend):
    config, backend = live_backend
    destination = config.projects_dir / "smoke" / "meta-ai.png"
    destination.parent.mkdir(parents=True, exist_ok=True)

    backend.generate(f"{config.style_prefix} {SCENE}", config.negative_prompt, 7, destination)

    width, height = png_size(destination)
    assert width >= 256 and height >= 256, "that is an icon, not a generated picture"
