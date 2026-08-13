"""MCP tool surface. Tools are mechanical: Claude does the creative work (ADR-0002)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .config import ChannelConfig, load_channel_config
from .runs import RunStore
from .script import Script, ScriptError, image_prompts_changed, narration_changed, parse_script

server = MCPServer("stickman_mcp", version="0.1.0")


@lru_cache(maxsize=1)
def channel_config() -> ChannelConfig:
    return load_channel_config()


def _runs() -> RunStore:
    return RunStore(channel_config().projects_dir)


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def _error(message: str) -> str:
    return f"Error: {message}"


def _unknown_run(run_id: str) -> str:
    return _error(f"no Run named '{run_id}'. Call stickman_create_run to start one.")


@server.tool(
    name="stickman_create_run",
    annotations=ToolAnnotations(title="Create Run", read_only_hint=False, idempotent_hint=False),
)
def stickman_create_run(topic: str, slug: str | None = None) -> str:
    """Start a new Run for a Topic and prepare its folder on disk.

    Args:
        topic: The one-line video idea, e.g. "How compound interest works".
        slug: Optional folder-name override; defaults to a slug of the topic.

    Returns:
        JSON: {"run_id": str, "path": str, "topic": str}
    """
    runs = _runs()
    run_id = runs.create(topic, slug)
    return _ok({"run_id": run_id, "path": str(runs.path(run_id)), "topic": topic})


@server.tool(
    name="stickman_save_script",
    annotations=ToolAnnotations(title="Save Script", read_only_hint=False, idempotent_hint=True),
)
def stickman_save_script(run_id: str, script: dict[str, Any]) -> str:
    """Validate and persist a Run's Script: the ordered Scenes narration and images derive from.

    Args:
        run_id: The Run returned by stickman_create_run.
        script: {"topic": str, "title": str, "visual_bible": {name: description}, "scenes":
            [{"id": int, "narration": str, "image_prompt": str}]}. Scene ids run sequentially
            from 1. Image prompts describe scene content only; the channel Style Prefix is
            applied by the server.

    Returns:
        JSON: {"run_id": str, "scene_count": int} plus "warning" when derived assets went stale.
        On failure an "Error: ..." string naming the problem; nothing is written.
    """
    runs = _runs()
    if not runs.exists(run_id):
        return _unknown_run(run_id)
    try:
        parsed = parse_script(script)
    except ScriptError as exc:
        return _error(f"{exc} Nothing was written; fix the script and call stickman_save_script again.")
    warning = _staleness_warning(runs, run_id, parsed)
    runs.save_script(run_id, parsed)
    payload: dict[str, Any] = {"run_id": run_id, "scene_count": len(parsed.scenes)}
    if warning:
        payload["warning"] = warning
    return _ok(payload)


def _staleness_warning(runs: RunStore, run_id: str, current: Script) -> str | None:
    """Name only the assets the new Script actually invalidates, so re-saving stays cheap."""
    try:
        previous = runs.load_script(run_id)
    except ScriptError:
        previous = None  # unreadable, so nothing on disk can be trusted to match
    stale = []
    clips = runs.narration_clip_count(run_id)
    if clips and (previous is None or narration_changed(previous, current)):
        stale.append(f"{clips} narration clip(s) in audio/ (stickman_synthesize_narration)")
    images = runs.image_count(run_id)
    if images and (previous is None or image_prompts_changed(previous, current)):
        stale.append(f"{images} image(s) in images/ (stickman_generate_images)")
    if not stale:
        return None
    return (
        "Assets generated from the previous Script are now stale: "
        + "; ".join(stale)
        + ". Delete the affected files, then re-run the tool named beside each, "
        "because those tools skip Scenes that already have assets."
    )


@server.tool(
    name="stickman_get_run",
    annotations=ToolAnnotations(title="Get Run Status", read_only_hint=True, idempotent_hint=True),
)
def stickman_get_run(run_id: str) -> str:
    """Report a Run's progress, derived from the files currently in its folder.

    Args:
        run_id: The Run returned by stickman_create_run.

    Returns:
        JSON: {"run_id": str, "path": str, "has_script": bool, "scene_count": int,
        "narration_clips": int, "images": int, "video_rendered": bool}.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    if not runs.exists(run_id):
        return _unknown_run(run_id)
    try:
        return _ok(runs.status(run_id))
    except ScriptError as exc:
        return _error(f"the saved script for '{run_id}' is unreadable: {exc} Call stickman_save_script to replace it.")


def main() -> None:
    channel_config()  # load eagerly so a broken config fails here, not mid-pipeline
    server.run()
