"""MCP tool surface. Tools are mechanical: Claude does the creative work (ADR-0002)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .config import ChannelConfig, load_channel_config
from .illustration import generate_images, redraw_scene, redraw_seed
from .images import ImageBackend, ImageError, SDXLLightningBackend
from .jobs import RUNNING, Job
from .metadata import build_metadata
from .narration import synthesize
from .render import RENDER_STEPS, RenderError, missing_asset_error, music_path, music_tracks, render
from .runs import RunStore
from .script import (
    Script,
    ScriptError,
    image_prompts_changed,
    narration_changed,
    parse_script,
    with_image_prompt,
)
from .tts import KokoroEngine, TTSEngine, TTSError

server = MCPServer("stickman_mcp", version="0.1.0")


@lru_cache(maxsize=1)
def channel_config() -> ChannelConfig:
    return load_channel_config()


@lru_cache(maxsize=1)
def tts_engine() -> TTSEngine:
    return KokoroEngine()


@lru_cache(maxsize=1)
def image_backend() -> ImageBackend:
    config = channel_config()
    return SDXLLightningBackend(config.image_width, config.image_height, config.image_steps, config.guidance_scale)


def _runs() -> RunStore:
    return RunStore(channel_config().projects_dir)


def _job(runs: RunStore, run_id: str) -> Job:
    return Job(runs.job_path(run_id))


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


def _error(message: str) -> str:
    return f"Error: {message}"


class ToolError(Exception):
    """A guard failed; the message is the Error: string the tool hands back."""


def _unknown_run(run_id: str) -> str:
    return _error(f"no Run named '{run_id}'. Call stickman_create_run to start one.")


def _unreadable_script(run_id: str, exc: ScriptError) -> str:
    return _error(f"the saved script for '{run_id}' is unreadable: {exc} Call stickman_save_script to replace it.")


def _script_for(runs: RunStore, run_id: str, doing: str) -> Script:
    """The guard every tool that reads a Script shares: known Run, readable Script, Script present."""
    if not runs.exists(run_id):
        raise ToolError(_unknown_run(run_id))
    try:
        script = runs.load_script(run_id)
    except ScriptError as exc:
        raise ToolError(_unreadable_script(run_id, exc)) from None
    if script is None:
        raise ToolError(_error(f"Run '{run_id}' has no Script to {doing}. Call stickman_save_script first."))
    return script


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
    spoken = previous is None or narration_changed(previous, current)
    drawn = previous is None or image_prompts_changed(previous, current)
    clips = runs.narration_clip_count(run_id)
    if clips and spoken:
        stale.append(f"{clips} narration clip(s) in audio/ (stickman_synthesize_narration)")
    images = runs.image_count(run_id)
    if images and drawn:
        stale.append(f"{images} image(s) in images/ (stickman_generate_images)")
    if (spoken or drawn) and runs.video_path(run_id).is_file():
        stale.append("the rendered video and its subtitles (stickman_render_video)")
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
        "narration_clips": int, "images": int, "video_rendered": bool, "subtitles": bool,
        "metadata": bool}, plus "job" holding the current or last background job when one
        has run (see stickman_job_status). The last three are the Video Package.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    if not runs.exists(run_id):
        return _unknown_run(run_id)
    try:
        status = runs.status(run_id)
    except ScriptError as exc:
        return _unreadable_script(run_id, exc)
    job = _job(runs, run_id).status()
    if job is not None:
        status["job"] = job
    return _ok(status)


@server.tool(
    name="stickman_synthesize_narration",
    annotations=ToolAnnotations(title="Synthesize Narration", read_only_hint=False, idempotent_hint=True),
)
def stickman_synthesize_narration(run_id: str) -> str:
    """Speak every Scene's Narration into a Narration Clip; a clip's length is its Scene's duration.

    A full Script takes minutes, so raise the client tool timeout (see README). Scenes that
    already have a clip are skipped, so calling again after a timeout finishes only the rest.

    Args:
        run_id: The Run returned by stickman_create_run, with a Script already saved.

    Returns:
        JSON: {"run_id": str, "scenes": [{"id": int, "duration_seconds": float}],
        "total_duration_seconds": float, "synthesized": int, "skipped": int}.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    try:
        script = _script_for(runs, run_id, "narrate")
    except ToolError as exc:
        return str(exc)
    try:
        config = channel_config()
        clips = synthesize(runs, run_id, script, tts_engine(), config.voice, config.voice_speed)
    except TTSError as exc:
        return _error(f"narration stopped: {exc} Clips already finished are kept.")
    scenes = [{"id": clip.scene_id, "duration_seconds": round(clip.duration_seconds, 3)} for clip in clips]
    return _ok(
        {
            "run_id": run_id,
            "scenes": scenes,
            "total_duration_seconds": round(sum(scene["duration_seconds"] for scene in scenes), 3),
            "synthesized": sum(1 for clip in clips if clip.synthesized),
            "skipped": sum(1 for clip in clips if not clip.synthesized),
        }
    )


@server.tool(
    name="stickman_generate_images",
    annotations=ToolAnnotations(title="Generate Images", read_only_hint=False, idempotent_hint=False),
)
def stickman_generate_images(run_id: str, only_missing: bool = False) -> str:
    """Start a background job drawing one still image per Scene; returns at once, so poll for progress.

    The channel Style Prefix and negative prompt are applied here, so Image Prompts describe scene
    content only. Seeds are the channel base seed plus the Scene id, so re-running repeats the batch.

    Args:
        run_id: The Run returned by stickman_create_run, with a Script already saved.
        only_missing: Draw only Scenes with no image yet; use this to finish a job that stopped.

    Returns:
        JSON: {"run_id": str, "job": "images", "state": "running", "done": 0, "total": int,
        "resume": str}. Poll stickman_job_status until state is done, then show the folder at
        the Image Review Checkpoint. On failure an "Error: ..." string naming the tool that
        fixes it.
    """
    runs = _runs()
    try:
        script = _script_for(runs, run_id, "illustrate")
    except ToolError as exc:
        return str(exc)
    job = _job(runs, run_id)
    running = _already_running(job, run_id)
    if running:
        return running
    config, backend = channel_config(), image_backend()
    started = job.start(
        "images",
        len(script.scenes),
        lambda: generate_images(runs, run_id, script, backend, config, only_missing),
        resume="Call stickman_generate_images with only_missing set to draw the Scenes it did not reach.",
    )
    return _ok({"run_id": run_id, **started})


@server.tool(
    name="stickman_render_video",
    annotations=ToolAnnotations(title="Render Video", read_only_hint=False, idempotent_hint=True),
)
def stickman_render_video(run_id: str, music_track: str | None = None) -> str:
    """Start a background job assembling the Video Package: subtitles then the 1080p MP4.

    Each Scene's image holds the screen for its Narration Clip plus the channel gap, hard cuts
    only, so the video is exactly as long as the narration plus one gap per Scene.

    Args:
        run_id: The Run returned by stickman_create_run, narrated and illustrated already.
        music_track: A file name from stickman_list_music, laid quietly under the narration at
            the channel's music level and looped or trimmed to fit. Omit it for narration only.

    Returns:
        JSON: {"run_id": str, "job": "render", "state": "running", "done": 0, "total": 3,
        "resume": str}. Poll stickman_job_status until state is done. On failure an
        "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    try:
        script = _script_for(runs, run_id, "render")
    except ToolError as exc:
        return str(exc)
    job = _job(runs, run_id)
    running = _already_running(job, run_id)  # asked first, or a half-drawn batch reads as a Run short of images
    if running:
        return running
    missing = missing_asset_error(runs, run_id, script)
    if missing:
        return _error(f"Run '{run_id}' is not ready to render. {missing}")
    config = channel_config()
    try:
        music = music_path(config, music_track) if music_track else None
    except RenderError as exc:
        return _error(f"{exc} Call stickman_list_music to see the folder.")
    started = job.start(
        "render",
        RENDER_STEPS,
        lambda: render(runs, run_id, script, config, music),
        resume="Call stickman_render_video again; it rebuilds the whole Video Package from scratch.",
    )
    return _ok({"run_id": run_id, **started})


@server.tool(
    name="stickman_list_music",
    annotations=ToolAnnotations(title="List Music", read_only_hint=True, idempotent_hint=True),
)
def stickman_list_music() -> str:
    """List the background music tracks in the channel's curated folder.

    Only tracks the creator put there are ever used, so a monetized video never risks a
    Content ID claim. Pass one of these names to stickman_render_video as music_track.

    Returns:
        JSON: {"music_dir": str, "tracks": [str]}. An empty list means the folder holds no
        audio files yet.
    """
    config = channel_config()
    return _ok({"music_dir": str(config.music_dir), "tracks": music_tracks(config)})


@server.tool(
    name="stickman_save_metadata",
    annotations=ToolAnnotations(title="Save Metadata", read_only_hint=False, idempotent_hint=True),
)
def stickman_save_metadata(run_id: str, title: str, description: str, tags: list[str]) -> str:
    """Complete the Video Package with the upload fields, written for copy-paste into YouTube.

    The saved description carries an AI-generation disclosure line, so what the creator pastes
    is already compliant. Remind them to tick YouTube's altered or synthetic content box too.

    Args:
        run_id: The Run returned by stickman_create_run.
        title: The video title.
        description: The video description; the disclosure line is appended for you.
        tags: Search tags, saved comma-joined the way YouTube's tag box wants them.

    Returns:
        JSON: {"run_id": str, "metadata": str, "tags": int}.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    if not runs.exists(run_id):
        return _unknown_run(run_id)
    cleaned = [tag.strip() for tag in tags if tag.strip()]
    if not title.strip() or not description.strip():
        return _error("title and description must both be non-empty. Nothing was written.")
    runs.save_metadata(run_id, build_metadata(title.strip(), description.strip(), cleaned))
    return _ok({"run_id": run_id, "metadata": str(runs.metadata_path(run_id)), "tags": len(cleaned)})


@server.tool(
    name="stickman_job_status",
    annotations=ToolAnnotations(title="Job Status", read_only_hint=True, idempotent_hint=True),
)
def stickman_job_status(run_id: str) -> str:
    """Report the Run's current or last background job. Poll this while a job runs.

    Args:
        run_id: The Run whose job to report.

    Returns:
        JSON: {"run_id": str, "job": str, "state": "running"|"done"|"error", "done": int,
        "total": int, "resume": str}, plus "error" with the failure message when state is
        error. done counts Scenes finished, including any skipped as already drawn.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    if not runs.exists(run_id):
        return _unknown_run(run_id)
    status = _job(runs, run_id).status()
    if status is None:
        return _error(f"no background job has run for '{run_id}'. Call stickman_generate_images to start one.")
    return _ok({"run_id": run_id, **status})


@server.tool(
    name="stickman_regenerate_image",
    annotations=ToolAnnotations(title="Regenerate Image", read_only_hint=False, idempotent_hint=False),
)
def stickman_regenerate_image(
    run_id: str, scene_id: int, image_prompt: str | None = None, seed: int | None = None
) -> str:
    """Redraw one Scene's image, replacing the file. Fast enough to call while the creator watches.

    Use at the Image Review Checkpoint. With no image_prompt and no seed this rerolls: same prompt,
    a new random seed, so the picture changes. A new image_prompt is saved into the Script before
    drawing, because the Script is the single source of truth for what a Scene shows.

    Args:
        run_id: The Run returned by stickman_create_run.
        scene_id: Which Scene to redraw, from 1 to the Script's scene count.
        image_prompt: Replacement scene content, when the picture is wrong rather than unlucky.
            Describe scene content only; the channel Style Prefix is applied by the server.
        seed: Reuse a specific seed to reproduce an image; omit it to reroll.

    Returns:
        JSON: {"run_id": str, "scene_id": int, "seed": int, "image": str, "image_prompt": str,
        "script_updated": bool}.
        On failure an "Error: ..." string naming the tool that fixes it.
    """
    runs = _runs()
    try:
        script = _script_for(runs, run_id, "illustrate")
    except ToolError as exc:
        return str(exc)
    if not 1 <= scene_id <= len(script.scenes):
        return _error(
            f"Run '{run_id}' has no Scene {scene_id}; its Script has Scenes 1 to {len(script.scenes)}. "
            "Call stickman_get_run to check the scene count, or stickman_save_script to change the Script."
        )
    job = _job(runs, run_id)
    running = _already_running(job, run_id)
    if running:
        return running
    if image_prompt is not None:
        try:
            script = with_image_prompt(script, scene_id, image_prompt)
        except ScriptError as exc:
            return _error(f"{exc} Nothing was written; call stickman_regenerate_image with a prompt.")
        runs.save_script(run_id, script)  # saved before drawing, so the file always explains the image
    config = channel_config()
    scene = script.scenes[scene_id - 1]
    chosen = redraw_seed(config, scene_id, seed)
    try:
        destination = redraw_scene(runs, run_id, scene, image_backend(), config, chosen)
    except ImageError as exc:
        return _error(f"{exc}. The Script keeps the Image Prompt; call stickman_regenerate_image to try again.")
    return _ok(
        {
            "run_id": run_id,
            "scene_id": scene_id,
            "seed": chosen,
            "image": str(destination),
            "image_prompt": scene.image_prompt,
            "script_updated": image_prompt is not None,
        }
    )


def _already_running(job: Job, run_id: str) -> str | None:
    """One job per Run: two jobs would write the same files and race over the GPU."""
    current = job.status()
    if current is None or current["state"] != RUNNING:
        return None
    return _error(
        f"a {current['job']} job is already running for '{run_id}' "
        f"({current['done']} of {current['total']} done). Call stickman_job_status to follow it."
    )


def main() -> None:
    channel_config()  # load eagerly so a broken config fails here, not mid-pipeline
    server.run()
