"""Channel-wide production settings, loaded once at server start."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV_VAR = "STICKMAN_CHANNEL_CONFIG"
CONFIG_FILENAME = "channel.toml"


class ConfigError(Exception):
    """The channel config is missing, unparseable, or holds an unusable value."""


@dataclass(frozen=True)
class ChannelConfig:
    source: Path
    projects_dir: Path
    music_dir: Path
    style_prefix: str
    negative_prompt: str
    voice: str
    voice_speed: float
    width: int
    height: int
    fps: int
    scene_gap_seconds: float
    music_level_db: float
    image_width: int
    image_height: int
    image_steps: int
    guidance_scale: float
    base_seed: int


def load_channel_config(path: Path | None = None) -> ChannelConfig:
    source = Path(path) if path is not None else default_config_path()
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(
            f"Cannot read the channel config at {source}: {exc.strerror}. "
            f"Restore it or point {CONFIG_ENV_VAR} at a valid file."
        ) from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{source} is not valid TOML: {exc}") from None

    read = _Reader(source, data)
    config = ChannelConfig(
        source=source,
        projects_dir=_resolve(source, read.text("paths", "projects_dir", "projects")),
        music_dir=_resolve(source, read.text("paths", "music_dir", "music")),
        style_prefix=read.text("style", "prefix"),
        negative_prompt=read.text("style", "negative_prompt"),
        voice=read.text("voice", "name", "af_heart"),
        voice_speed=read.number("voice", "speed", 1.0, minimum=0.5),
        width=read.whole("render", "width", 1920),
        height=read.whole("render", "height", 1080),
        fps=read.whole("render", "fps", 30),
        scene_gap_seconds=read.number("render", "scene_gap_seconds", 0.4, minimum=0.0),
        music_level_db=read.number("render", "music_level_db", -22.0, minimum=-60.0),
        image_width=read.whole("image", "width", 1344),
        image_height=read.whole("image", "height", 768),
        image_steps=read.whole("image", "steps", 4),
        guidance_scale=read.number("image", "guidance_scale", 1.0, minimum=0.0),
        base_seed=read.whole("image", "base_seed", 20260813, minimum=0),
    )
    read.reject_unknown()
    return config


class _Reader:
    """Typed access to the parsed config, tracking which settings were recognised."""

    def __init__(self, source: Path, data: dict[str, Any]) -> None:
        self.source = source
        self.data = data
        self.known: set[str] = set()

    def text(self, section: str, key: str, default: str | None = None) -> str:
        value = self._value(section, key, default)
        if not isinstance(value, str) or not value.strip():
            raise self._invalid(section, key, "a non-empty string", value)
        return value.strip()

    def whole(self, section: str, key: str, default: int, minimum: int = 1) -> int:
        value = self._value(section, key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise self._invalid(section, key, f"a whole number >= {minimum}", value)
        return value

    def number(self, section: str, key: str, default: float, minimum: float) -> float:
        value = self._value(section, key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
            raise self._invalid(section, key, f"a number >= {minimum}", value)
        return float(value)

    def reject_unknown(self) -> None:
        unknown = []
        for section, table in self.data.items():
            if not isinstance(table, dict):
                unknown.append(section)
                continue
            unknown += [f"{section}.{key}" for key in table if f"{section}.{key}" not in self.known]
        if unknown:
            raise ConfigError(
                f"{self.source}: unknown setting(s) {', '.join(sorted(unknown))}. "
                "Check for a typo against the shipped channel.toml."
            )

    def _value(self, section: str, key: str, default: Any) -> Any:
        self.known.add(f"{section}.{key}")
        table = self.data.get(section, {})
        if not isinstance(table, dict):
            raise ConfigError(f"{self.source}: [{section}] must be a section, got {table!r}")
        value = table.get(key, default)
        if value is None:
            raise ConfigError(f"{self.source}: {section}.{key} is required and has no default")
        return value

    def _invalid(self, section: str, key: str, expected: str, value: Any) -> ConfigError:
        return ConfigError(f"{self.source}: {section}.{key} must be {expected}, got {value!r}")


def default_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV_VAR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / CONFIG_FILENAME


def _resolve(source: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else source.parent / candidate
