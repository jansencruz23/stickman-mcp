"""Script and Scene: the ordered narration Claude authors before any synthesis (ADR-0001)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any


ILLUSTRATIVE = "illustrative"
NARRATIVE = "narrative"
FORMATS = (ILLUSTRATIVE, NARRATIVE)


class ScriptError(Exception):
    """The submitted Script does not satisfy the Scene contract."""


@dataclass(frozen=True)
class Scene:
    id: int
    narration: str
    image_prompt: str
    card: bool = False  # a ranking or chapter screen, the one kind of Scene whose words are the point
    clauses: tuple[str, ...] = ()  # style clauses this Scene needs, by name; none is the safe default
    establishes: bool = False  # opens a Beat Group, and its image becomes that group's setting reference
    lead: bool = False  # this Scene holds the Lead, so the Lead sheet rides with it


@dataclass(frozen=True)
class Script:
    topic: str
    title: str
    scenes: tuple[Scene, ...]
    visual_bible: Mapping[str, str] = field(default_factory=dict)
    format: str = ILLUSTRATIVE


def beat_groups(script: Script) -> tuple[tuple[int, ...], ...]:
    """Scene ids per Beat Group, establisher first. Empty outside the narrative format, which has none."""
    if script.format != NARRATIVE:
        return ()
    groups: list[list[int]] = []
    for scene in script.scenes:
        if scene.establishes:
            groups.append([scene.id])
        elif groups:
            groups[-1].append(scene.id)
    return tuple(tuple(group) for group in groups)


def establisher_for(script: Script, scene_id: int) -> int | None:
    """Which Scene opens this one's Beat Group. Itself when it is the establisher; None when it has no group."""
    for group in beat_groups(script):
        if scene_id in group:
            return group[0]
    return None


def group_of(script: Script, establisher_id: int) -> tuple[int, ...]:
    """The Scenes drawn from one establisher, excluding the establisher itself."""
    for group in beat_groups(script):
        if group[0] == establisher_id:
            return group[1:]
    return ()


def parse_script(data: Any) -> Script:
    if not isinstance(data, Mapping):
        raise ScriptError("script must be an object with topic, title and scenes.")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise ScriptError("script.scenes must be a non-empty list of Scenes.")
    scenes = tuple(_scene(raw, position) for position, raw in enumerate(raw_scenes, start=1))
    _require_sequential_ids(scenes)
    script = Script(
        topic=_text(data, "topic", "script"),
        title=_text(data, "title", "script"),
        scenes=scenes,
        visual_bible=_visual_bible(data.get("visual_bible", {})),
        format=_format(data.get("format", ILLUSTRATIVE)),
    )
    _require_consistent_format(script)
    return script


def script_to_dict(script: Script) -> dict[str, Any]:
    return {
        "topic": script.topic,
        "title": script.title,
        "format": script.format,
        "visual_bible": dict(script.visual_bible),
        "scenes": [
            {"id": scene.id, "narration": scene.narration, "image_prompt": scene.image_prompt}
            | ({"card": True} if scene.card else {})
            | ({"clauses": list(scene.clauses)} if scene.clauses else {})
            | ({"establishes": True} if scene.establishes else {})
            | ({"lead": True} if scene.lead else {})
            for scene in script.scenes
        ],
    }


def with_image_prompt(script: Script, scene_id: int, image_prompt: str) -> Script:
    """Replace one Scene's Image Prompt; callers save the result, keeping the Script the source of truth."""
    replacement = image_prompt.strip()
    if not replacement:
        raise ScriptError(f"scene {scene_id}.image_prompt must be a non-empty string.")
    scenes = tuple(
        replace(scene, image_prompt=replacement) if scene.id == scene_id else scene for scene in script.scenes
    )
    return replace(script, scenes=scenes)


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
    return Scene(
        id=scene_id,
        narration=_text(raw, "narration", where),
        image_prompt=_text(raw, "image_prompt", where),
        card=_flag(raw, "card", where),
        clauses=_clauses(raw.get("clauses", ()), where),
        establishes=_flag(raw, "establishes", where),
        lead=_flag(raw, "lead", where),
    )


def _flag(raw: Mapping[str, Any], key: str, where: str) -> bool:
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise ScriptError(f"{where}.{key} must be true or false.")
    return value


def _format(raw: Any) -> str:
    if raw not in FORMATS:
        raise ScriptError(f"script.format must be one of {', '.join(FORMATS)}; got {raw!r}.")
    return str(raw)


def _require_consistent_format(script: Script) -> None:
    """Beat Groups are the narrative format's whole mechanism, so establishes has no meaning without it."""
    if script.format != NARRATIVE:
        stray = [scene.id for scene in script.scenes if scene.establishes]
        if stray:
            raise ScriptError(
                f"scene {stray[0]} sets establishes, which only the narrative format uses. "
                'Set "format": "narrative" or drop the flag.'
            )
        return
    if not script.scenes[0].establishes:
        raise ScriptError(
            "scene 1 must set establishes in the narrative format, or the Scenes before the first "
            "establishing shot belong to no Beat Group and have no setting reference."
        )


def _clauses(raw: Any, where: str) -> tuple[str, ...]:
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise ScriptError(f"{where}.clauses must be a list of clause names.")
    if not all(isinstance(name, str) and name.strip() for name in raw):
        raise ScriptError(f"{where}.clauses must hold non-empty strings.")
    return tuple(name.strip() for name in raw)


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
