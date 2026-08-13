import pytest

from stickman_mcp import server
from stickman_mcp.config import CONFIG_ENV_VAR, load_channel_config

TEST_CHANNEL = """
[paths]
projects_dir = "projects"
music_dir = "music"

[style]
prefix = "test stickman style,"
negative_prompt = "photo"
"""


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
