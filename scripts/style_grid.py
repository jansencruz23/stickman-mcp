"""One-off: draw candidate Style Prefixes against the same prompts, so the channel look is picked from real output.

Run with: uv run python scripts/style_grid.py [--guidance 3.0]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stickman_mcp.config import load_channel_config
from stickman_mcp.images import SDXLLightningBackend

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "tuning" / "style-grid"

# The 2026-08-16 audition set, all rejected in favour of the coloured cartoon look now in channel.toml.
# The grid always renders the locked prefix as "current", so a re-run compares alternatives against it.
CANDIDATES = {
    "ink-line": (
        "black ink line art of stick figures, thin uniform outline, no shading, no fill, "
        "pure white background, xkcd webcomic style,"
    ),
    "whiteboard": (
        "whiteboard marker drawing, simple black stick figure doodle drawn with a dry erase marker "
        "on a clean white board, no colour, no shading,"
    ),
    "coloring-book": (
        "coloring book page, bold black outlines only, stick figure characters, completely white "
        "background, flat, no shading, no grey, no fill,"
    ),
    "notebook-doodle": (
        "simple ballpoint pen doodle on plain white paper, stick figure with a circle head and "
        "straight limbs, thin sketchy lines, no shading,"
    ),
    "bold-marker": (
        "thick black marker stick figure drawing, chunky uniform strokes, circle head, straight "
        "stick limbs, flat white background, high contrast, no gradients,"
    ),
    "flat-icon": (
        "flat minimal vector icon illustration, black stick figure with a circle head, plain white "
        "background, uniform line weight, no gradients, no texture,"
    ),
}

SUBJECTS = {
    "coin": "a stick figure standing beside a giant coin and pointing at it",
    "chart": "a stick figure climbing a line chart that curves upward",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the channel style grid.")
    parser.add_argument("--guidance", type=float, help="override image.guidance_scale for this grid")
    override = parser.parse_args().guidance

    config = load_channel_config()
    styles = {"current": config.style_prefix} | CANDIDATES
    guidance = config.guidance_scale if override is None else override
    backend = SDXLLightningBackend(config.image_width, config.image_height, config.image_steps, guidance)

    # Guidance gets its own folder, so comparing settings never overwrites the grid being compared against.
    output_dir = OUTPUT_ROOT / f"guidance-{guidance}"
    output_dir.mkdir(parents=True, exist_ok=True)
    legend = output_dir / "styles.txt"
    legend.write_text("".join(f"{name}: {prefix}\n" for name, prefix in styles.items()), encoding="utf-8")

    for style, prefix in styles.items():
        for offset, (subject, scene) in enumerate(SUBJECTS.items()):
            destination = output_dir / f"{style}--{subject}.png"
            # One seed per subject, shared by every style, so only the prefix varies between rows.
            backend.generate(f"{prefix} {scene}", config.negative_prompt, config.base_seed + offset, destination)
            print(destination.name)

    print(f"\n{len(styles) * len(SUBJECTS)} images and {legend.name} in {output_dir}")


if __name__ == "__main__":
    main()
