import pytest

from stickman_mcp import server
from stickman_mcp.config import CONFIG_ENV_VAR, ConfigError


def test_broken_channel_config_stops_startup_before_the_server_serves(tmp_path, monkeypatch):
    broken = tmp_path / "channel.toml"
    broken.write_text("[style\nprefix = 'x'\n", encoding="utf-8")
    monkeypatch.setenv(CONFIG_ENV_VAR, str(broken))
    served = []
    monkeypatch.setattr(server.server, "run", lambda *args, **kwargs: served.append(True))

    with pytest.raises(ConfigError) as caught:
        server.main()

    assert str(broken) in str(caught.value)
    assert served == []
