"""One-off: draw candidate Style Prefixes against the same prompts, so the channel look is picked from real output.

Draws through whichever backend channel.toml selects, so the grid tests the look a Run would ship.

Run with: uv run python scripts/style_grid.py [--guidance 3.0]
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from stickman_mcp.config import ChannelConfig, load_channel_config
from stickman_mcp.illustration import backend_for
from stickman_mcp.images import SDXL

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "tuning" / "style-grid"

# Variations on the 2026-08-22 crude relock, each pushing the hand-made look a different way.
# The grid always renders the locked prefix as "current", so a re-run compares alternatives against it.
CANDIDATES = {
    "crayon-scrawl": (
        "16:9 widescreen landscape frame, much wider than it is tall, rough childlike crayon scrawl, "
        "people drawn as lopsided stick figures with big wobbly circle heads, uneven dot eyes, "
        "thin crooked stick arms and legs, animals drawn as ordinary four legged cartoon animals "
        "with solid furry bodies and real animal heads, messy uneven outlines, "
        "colour scribbled well past the lines, wide 16:9 landscape composition,"
    ),
    "marker-doodle": (
        "16:9 widescreen landscape frame, much wider than it is tall, quick felt tip marker doodle, "
        "people drawn as stick figures with big round wonky cream heads and dot eyes, thin shaky "
        "black stick limbs, animals drawn as ordinary four legged cartoon animals with solid furry "
        "bodies and real animal heads, blotchy uneven marker outlines, flat patchy colour, "
        "wide 16:9 landscape composition,"
    ),
    "sloppy-paint": (
        "16:9 widescreen landscape frame, much wider than it is tall, sloppy cartoon drawn with a "
        "mouse in a basic paint program, people drawn as stick figures with big lopsided cream "
        "circle heads and dot eyes, thin wobbling stick limbs, animals drawn as ordinary four "
        "legged cartoon animals with solid furry bodies and real animal heads, jagged uneven "
        "outlines, flat colour spilling outside the lines, wide 16:9 landscape composition,"
    ),
}

# One subject per thing the prefix asserts: crude linework on a person, and animals staying animals.
SUBJECTS = {
    "person": "a stick figure man standing at the edge of a cliff looking down at a river far below",
    "animal": "a wolf howling in a snowy forest at night",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the channel style grid.")
    parser.add_argument("--guidance", type=float, help="override image.guidance_scale; sdxl only")
    parser.add_argument("--locked-only", action="store_true", help="draw the locked prefix and no candidates")
    options = parser.parse_args()

    config = load_channel_config()
    if options.guidance is not None:
        config = replace(config, guidance_scale=options.guidance)
    styles = {"current": config.style_prefix}
    if not options.locked_only:
        styles |= CANDIDATES

    output_dir = OUTPUT_ROOT / _grid_name(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    legend = output_dir / "styles.txt"
    legend.write_text("".join(f"{name}: {prefix}\n" for name, prefix in styles.items()), encoding="utf-8")

    backend = backend_for(config)
    try:
        for style, prefix in styles.items():
            for offset, (subject, scene) in enumerate(SUBJECTS.items()):
                destination = output_dir / f"{style}--{subject}.png"
                # One seed per subject, shared by every style, so only the prefix varies between rows.
                backend.generate(f"{prefix} {scene}", config.negative_prompt, config.base_seed + offset, destination)
                print(destination.name, flush=True)
    finally:
        backend.close()

    print(f"\n{len(styles) * len(SUBJECTS)} images and {legend.name} in {output_dir}")


def _grid_name(config: ChannelConfig) -> str:
    """Guidance only bites on sdxl, so only its folders are split by the value."""
    if config.image_backend == SDXL:
        return f"guidance-{config.guidance_scale}"
    return config.image_backend


if __name__ == "__main__":
    main()
