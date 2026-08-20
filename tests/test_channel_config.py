from pathlib import Path

import pytest
from conftest import SHIPPED_CONFIG

from stickman_mcp.config import ConfigError, load_channel_config

LOCKED_STYLE_PREFIX = (
    "flat 2d cartoon illustration, stick figure characters with big round cream circle heads, "
    "simple dot eyes and thin eyebrows, plain thin black stick arms and legs drawn as unbroken lines, "
    "bold clean black outlines, flat muted colour fills, simple cel shaded scenery, no gradients,"
)


def test_the_shipped_config_carries_the_locked_channel_identity():
    """The tuning session's whole output. Changing these is a channel decision, not a passing edit."""
    config = load_channel_config(SHIPPED_CONFIG)

    assert config.style_prefix == LOCKED_STYLE_PREFIX
    assert (config.voice, config.voice_speed) == ("am_puck", 1.15)
    negatives = config.negative_prompt
    assert not any(word in negatives for word in ("color", "colour")), "the locked look is coloured"


def test_shipped_config_loads_documented_defaults():
    config = load_channel_config(SHIPPED_CONFIG)

    assert config.voice
    assert config.style_prefix.strip()
    assert config.scene_gap_seconds == 0.4
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
