from pathlib import Path

import pytest
from conftest import SHIPPED_CONFIG

from stickman_mcp.config import ConfigError, load_channel_config

LOCKED_STYLE_PREFIX = (
    "16:9 widescreen landscape frame, much wider than it is tall, flat 2d cartoon illustration, "
    "any people are drawn as stick figures with big round slightly lopsided cream circle heads, "
    "exactly two small solid black dots for eyes and one short flat black line above each eye, "
    "plain thin black stick arms and legs drawn as unbroken slightly wobbly lines, "
    "any animals are drawn as ordinary four legged cartoon animals with solid furry bodies and real animal heads, "
    "bold uneven hand inked black outlines, flat muted colour fills, simple flat scenery, no gradients, "
    "wide 16:9 landscape composition,"
)


def test_the_shipped_config_carries_the_locked_channel_identity():
    """The tuning session's whole output. Changing these is a channel decision, not a passing edit."""
    config = load_channel_config(SHIPPED_CONFIG)

    assert config.style_prefix == LOCKED_STYLE_PREFIX
    assert (config.voice, config.voice_speed) == ("am_puck", 1.0)
    negatives = config.negative_prompt
    assert not any(word in negatives for word in ("color", "colour")), "the locked look is coloured"
    assert "stick figure animals" in negatives, "only people are stick figures"
    assert "clean vector art" in negatives, "the locked look is hand made, not polished"
    assert "paper texture" in negatives, "hand made means uneven lines, not a drawing on paper"
    assert config.style_prefix.count("any ") == 2, "people and animals are described only if the Scene has them"
    assert config.style_prefix.startswith("16:9"), "the aspect clause leads, or Meta ignores it"


def test_shipped_config_loads_documented_defaults():
    config = load_channel_config(SHIPPED_CONFIG)

    assert config.voice
    assert config.style_prefix.strip()
    assert config.scene_gap_seconds == 0.0
    assert (config.width, config.height, config.fps) == (1920, 1080, 30)


def test_missing_config_names_the_expected_path(tmp_path):
    missing = tmp_path / "channel.toml"

    with pytest.raises(ConfigError) as caught:
        load_channel_config(missing)

    assert str(missing) in str(caught.value)


def test_unparseable_config_names_the_file(tmp_path):
    broken = tmp_path / "channel.toml"
    broken.write_text("[style\nprefix = 'x'\n", encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_channel_config(broken)

    assert str(broken) in str(caught.value)


def _write_config(tmp_path, body: str) -> Path:
    source = tmp_path / "channel.toml"
    source.write_text(
        "[style]\nprefix = 'stickman,'\nnegative_prompt = 'photo'\n" + body,
        encoding="utf-8",
    )
    return source


def test_out_of_range_value_names_the_setting(tmp_path):
    source = _write_config(tmp_path, "[render]\nfps = 0\n")

    with pytest.raises(ConfigError) as caught:
        load_channel_config(source)

    assert "render.fps" in str(caught.value)


def test_misspelled_setting_is_rejected_by_name(tmp_path):
    source = _write_config(tmp_path, "[render]\nfsp = 30\n")

    with pytest.raises(ConfigError) as caught:
        load_channel_config(source)

    assert "render.fsp" in str(caught.value)


def test_missing_locked_style_prefix_names_the_setting(tmp_path):
    source = tmp_path / "channel.toml"
    source.write_text("[style]\nnegative_prompt = 'photo'\n", encoding="utf-8")

    with pytest.raises(ConfigError) as caught:
        load_channel_config(source)

    assert "style.prefix" in str(caught.value)
