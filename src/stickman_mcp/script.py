"""Script and Scene: the ordered narration Claude authors before any synthesis (ADR-0001)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class ScriptError(Exception):
    """The submitted Script does not satisfy the Scene contract."""


@dataclass(frozen=True)
class Scene:
    id: int
    narration: str
    image_prompt: str
    card: bool = False  # a ranking or chapter screen, the one kind of Scene whose words are the point


@dataclass(frozen=True)
class Script:
    topic: str
    title: str
    scenes: tuple[Scene, ...]
    visual_bible: Mapping[str, str] = field(default_factory=dict)


def parse_script(data: Any) -> Script:
    if not isinstance(data, Mapping):
        raise ScriptError("script must be an object with topic, title and scenes.")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ScriptError("script.scenes must be a non-empty list of Scenes.")
    scenes = tuple(_scene(raw, position) for position, raw in enumerate(raw_scenes, start=1))
    _require_sequential_ids(scenes)
    return Script(
        topic=_text(data, "topic", "script"),
        title=_text(data, "title", "script"),
        scenes=scenes,
        visual_bible=_visual_bible(data.get("visual_bible", {})),
    )


def script_to_dict(script: Script) -> dict[str, Any]:
    return {
        "topic": script.topic,
        "title": script.title,
        "visual_bible": dict(script.visual_bible),
        "scenes": [
            {"id": scene.id, "narration": scene.narration, "image_prompt": scene.image_prompt}
            | ({"card": True} if scene.card else {})
            for scene in script.scenes
        ],
    }


def with_image_prompt(script: Script, scene_id: int, image_prompt: str) -> Script:
    """Replace one Scene's Image Prompt; callers save the result, keeping the Script the source of truth."""
    replacement = image_prompt.strip()
    if not replacement:
        raise ScriptError(f"scene {scene_id}.image_prompt must be a non-empty string.")
    scenes = tuple(
        Scene(scene.id, scene.narration, replacement, scene.card) if scene.id == scene_id else scene
        for scene in script.scenes
    )
    return Script(script.topic, script.title, scenes, script.visual_bible)


def narration_changed(previous: Script, current: Script) -> bool:
    return [scene.narration for scene in previous.scenes] != [scene.narration for scene in current.scenes]


def image_prompts_changed(previous: Script, current: Script) -> bool:
    return [scene.image_prompt for scene in previous.scenes] != [scene.image_prompt for scene in current.scenes]


def _scene(raw: Any, position: int) -> Scene:
    if not isinstance(raw, Mapping):
        raise ScriptError(f"scene at position {position} must be an object with id, narration and image_prompt.")
    scene_id = raw.get("id")
    if isinstance(scene_id, bool) or not isinstance(scene_id, int):
        raise ScriptError(f"scene at position {position} has a non-integer id {scene_id!r}.")
    where = f"scene {scene_id}"
    card = raw.get("card", False)
    if not isinstance(card, bool):
        raise ScriptError(f"{where}.card must be true or false.")
    return Scene(
        id=scene_id,
        narration=_text(raw, "narration", where),
        image_prompt=_text(raw, "image_prompt", where),
        card=card,
    )


def _require_sequential_ids(scenes: tuple[Scene, ...]) -> None:
    found = [scene.id for scene in scenes]
    expected = list(range(1, len(scenes) + 1))
    if found != expected:
        raise ScriptError(
            f"scene ids must run sequentially from 1 with no gaps or reordering; "
            f"got {_join(found)} but expected {_join(expected)}."
        )


def _join(ids: list[int]) -> str:
    return ", ".join(str(scene_id) for scene_id in ids)


def _visual_bible(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping) or any(not isinstance(v, str) for v in raw.values()):
        raise ScriptError("script.visual_bible must map each recurring name to one description string.")
    return {str(name): description.strip() for name, description in raw.items()}


def _text(data: Mapping[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScriptError(f"{where}.{key} must be a non-empty string.")
    return value.strip()
