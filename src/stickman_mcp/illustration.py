"""Batch illustration: one still per Scene, with the channel's style applied server-side."""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence
from pathlib import Path

from .config import ChannelConfig
from .images import META_AI, ImageBackend, ImageError, SDXLLightningBackend
from .meta_ai import MetaAIBackend, PlaywrightMetaChat
from .runs import RunStore
from .script import Scene, Script, ScriptError

MAX_SEED = 2**31 - 1

# Lifted for card Scenes only. Left in place they fight the very thing a ranking screen is for.
TEXT_BANS = ("text", "watermark", "signature")


def backend_for(config: ChannelConfig) -> ImageBackend:
    """The one place image.backend becomes a live backend, so a tuning grid draws what a Run draws."""
    if config.image_backend == META_AI:
        return MetaAIBackend(
            lambda: PlaywrightMetaChat(config.meta_profile_dir, config.meta_timeout_seconds),
            config.meta_delay_seconds,
        )
    return SDXLLightningBackend(config.image_width, config.image_height, config.image_steps, config.guidance_scale)


def generate_images(
    runs: RunStore,
    run_id: str,
    script: Script,
    backend: ImageBackend,
    config: ChannelConfig,
    only_missing: bool,
) -> Iterator[int]:
    """Yields each finished Scene id, so the caller can report progress without waiting for the batch."""
    try:
        for scene in script.scenes:
            destination = runs.image_path(run_id, scene.id)
            if not (only_missing and destination.is_file()):
                prompt = compose_prompt(scene, prefix_for(scene, config))
                draw(
                    destination,
                    prompt,
                    negative_for(scene, config),
                    scene_seed(config, scene.id),
                    backend,
                    references_for(scene, runs, run_id),
                )
            yield scene.id
    finally:
        backend.close()  # one batch is one browser session, however many threads it opens inside


def redraw_scene(
    runs: RunStore,
    run_id: str,
    scene: Scene,
    backend: ImageBackend,
    config: ChannelConfig,
    seed: int,
) -> Path:
    """One Scene, one seed, same composition as the batch: a redraw differs only by seed and prompt."""
    destination = runs.image_path(run_id, scene.id)
    prompt = compose_prompt(scene, prefix_for(scene, config))
    references = references_for(scene, runs, run_id)
    try:
        draw(destination, prompt, negative_for(scene, config), seed, backend, references)
    finally:
        backend.close()
    return destination


def references_for(scene: Scene, runs: RunStore, run_id: str) -> tuple[Path, ...]:
    """The Lead sheet, on the Scenes that opted in. Meta reads only the first attachment, so there is
    never a second: a setting picture sent alongside is ignored, and sent first it costs the Lead."""
    lead = runs.lead_path(run_id)
    if scene.lead and lead.is_file():
        return (lead,)
    return ()


def draw(
    destination: Path,
    prompt: str,
    negative_prompt: str,
    seed: int,
    backend: ImageBackend,
    references: Sequence[Path] = (),
) -> None:
    """Publish by rename, so an interrupted image is never mistaken for a finished one on resume."""
    partial = destination.with_name(destination.name + ".part")
    try:
        backend.generate(prompt, negative_prompt, seed, partial, references)
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"the image backend failed on {destination.name}: {exc}") from None
    partial.replace(destination)


def negative_for(scene: Scene, config: ChannelConfig) -> str:
    """channel.toml stays the only place the negative prompt is written; a card just drops the text bans."""
    if not scene.card:
        return config.negative_prompt
    kept = [term.strip() for term in config.negative_prompt.split(",") if term.strip() not in TEXT_BANS]
    return ", ".join(kept)


def prefix_for(scene: Scene, config: ChannelConfig) -> str:
    """Meta supplies whatever the prefix names, so a subject clause rides only on the Scenes that have one."""
    if not scene.clauses:
        return config.style_prefix
    missing = [name for name in scene.clauses if name not in config.clauses]
    if missing:
        raise ScriptError(f"scene {scene.id} asks for {missing}; {config.source.name} offers {sorted(config.clauses)}")
    return " ".join([config.style_prefix] + [config.clauses[name] for name in scene.clauses])


def compose_prompt(scene: Scene, style_prefix: str) -> str:
    """Style is mechanical, so the server owns it and Claude's prompts describe scene content only."""
    return f"{style_prefix} {scene.image_prompt}"


def scene_seed(config: ChannelConfig, scene_id: int) -> int:
    return config.base_seed + scene_id


def redraw_seed(config: ChannelConfig, scene_id: int, seed: int | None) -> int:
    """No seed means reroll, and never the batch seed, so asking again always draws a different image."""
    batch = scene_seed(config, scene_id)
    if seed is not None:
        return seed
    rerolled = batch
    while rerolled == batch:
        rerolled = random.randrange(MAX_SEED)
    return rerolled


def audition_lead(
    runs: RunStore,
    run_id: str,
    sheet_prompt: str,
    candidates: int,
    backend: ImageBackend,
    config: ChannelConfig,
) -> Iterator[int]:
    """Draws the Lead candidates a creator picks between. Each is one sheet, so each is one attachment."""
    try:
        for candidate in range(1, candidates + 1):
            destination = runs.lead_candidate_path(run_id, candidate)
            prompt = f"{config.style_prefix} {sheet_prompt}"
            draw(destination, prompt, config.negative_prompt, config.base_seed + candidate, backend)
            yield candidate
    finally:
        backend.close()
