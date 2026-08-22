"""Batch illustration: one still per Scene, with the channel's style applied server-side."""

from __future__ import annotations

import random
from collections.abc import Iterator
from pathlib import Path

from .config import ChannelConfig
from .images import META_AI, ImageBackend, ImageError, SDXLLightningBackend
from .meta_ai import MetaAIBackend, PlaywrightMetaChat
from .runs import RunStore
from .script import Scene, Script

MAX_SEED = 2**31 - 1


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
                prompt = compose_prompt(scene, config.style_prefix)
                draw(destination, prompt, config.negative_prompt, scene_seed(config, scene.id), backend)
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
    prompt = compose_prompt(scene, config.style_prefix)
    try:
        draw(destination, prompt, config.negative_prompt, seed, backend)
    finally:
        backend.close()
    return destination


def draw(destination: Path, prompt: str, negative_prompt: str, seed: int, backend: ImageBackend) -> None:
    """Publish by rename, so an interrupted image is never mistaken for a finished one on resume."""
    partial = destination.with_name(destination.name + ".part")
    try:
        backend.generate(prompt, negative_prompt, seed, partial)
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError(f"the image backend failed on {destination.name}: {exc}") from None
    partial.replace(destination)


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
