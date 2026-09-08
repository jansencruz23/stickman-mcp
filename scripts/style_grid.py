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

CLOSING = "wide 16:9 landscape composition,"

# Channel two draws creatures, which the locked prefix is deliberately silent about. Each candidate
# below changes only the creature clause, so a difference in the grid has one cause.
CREATURE_CLAUSES = {
    "creature-solid": (
        "any creature is drawn as a solid filled cartoon animal with a real animal head "
        "and its own real anatomy,"
    ),
    "creature-pinned": (
        "any creature is drawn as a solid filled cartoon animal with a real animal head, its own "
        "real body shape and its own real number of limbs, never with a round human head, "
        "never with thin stick legs,"
    ),
}

# The one candidate that is not a clause swap: it drops the stick figure people entirely, to answer
# whether channel two should look like channel one at all.
CREATURES_NO_PEOPLE = (
    "16:9 widescreen landscape frame, much wider than it is tall, flat 2d cartoon illustration, "
    "any creature is drawn as a solid filled cartoon animal with a real animal head, its own real "
    "body shape and its own real number of limbs, bold uneven hand inked black outlines, "
    "flat muted colour fills, simple flat scenery, no gradients, " + CLOSING
)

# The four cases a creature channel actually ships: no clear body plan, a familiar silhouette,
# a body plan that is neither furry nor four legged, and a creature sharing the frame with a person.
CREATURE_SUBJECTS = {
    "tapeworm": "a long flat tapeworm coiled in a pale loop on a dark surface, its hooked head end raised",
    "dinosaur": "a tyrannosaurus standing in a fern forest, head lowered, mouth slightly open",
    "anglerfish": "an anglerfish in black deep water, its glowing lure hanging in front of its long teeth",
    "whale-scale": "a stick figure man standing beside an enormous blue whale, dwarfed by it, for scale",
}


def creature_styles(locked: str) -> dict[str, str]:
    """The creature clause sits before the closing aspect clause, which has to stay last."""
    styles = {"current": locked}
    for name, clause in CREATURE_CLAUSES.items():
        styles[name] = locked.replace(CLOSING, f"{clause} {CLOSING}")
    styles["no-people"] = CREATURES_NO_PEOPLE
    return styles


# One subject per thing the prefix asserts. "object" earns its place: the prefix describes how people
# and animals look, and Meta read that as a promise they are present, staging still lifes in a meadow
# with bystanders. A subject with neither is the only one that catches it.
SUBJECTS = {
    "person": "a stick figure man standing at the edge of a cliff looking down at a river far below",
    "animal": "a wolf howling in a snowy forest at night",
    "object": "a coiled length of intestine cut open on a metal tray, showing pale threads inside",
}


# The anime channel's prefix is a placeholder, and the 2026-09-08 probe showed why it cannot ship:
# Meta drew good anime every time and never the same anime twice - flat cel, watercolour, painterly
# and bright generic across ten images. "anime illustration" names no medium. Each candidate below
# pins the same four things channel one's locked prefix pins: line quality, how it is shaded, the
# palette, and how the background is treated. Whichever holds across all three subjects gets written
# into channel-anime.toml with its negative prompt built from what the losers did wrong.
ANIME_CANDIDATES = {
    "flat-cel": (
        "16:9 widescreen landscape frame, much wider than it is tall, flat 2d anime cel animation "
        "still, clean even black outlines of constant weight, flat blocks of colour with one hard "
        "edged shadow tone and no soft gradients, bright saturated palette, simple uncluttered "
        "backgrounds, " + CLOSING
    ),
    "soft-cel": (
        "16:9 widescreen landscape frame, much wider than it is tall, modern television anime still, "
        "fine clean dark linework, soft cel shading with gentle gradients on skin and hair, warm "
        "naturalistic palette, detailed but calm backgrounds, " + CLOSING
    ),
    "retro-cel": (
        "16:9 widescreen landscape frame, much wider than it is tall, 1990s hand painted anime cel, "
        "heavy uneven black ink lines, flat gouache colour with hard shadow shapes, muted slightly "
        "faded palette, painted backgrounds with visible brushwork, film grain, " + CLOSING
    ),
    "painted": (
        "16:9 widescreen landscape frame, much wider than it is tall, painted anime background art, "
        "soft brushed edges rather than hard outlines, layered watercolour and gouache washes, "
        "muted natural palette, deep atmospheric backgrounds, " + CLOSING
    ),
}

# What a story channel actually ships: one person close enough to read a face, an interior that has
# to hold still across a Beat Group, and an exterior with nobody in it. The last one catches a prefix
# that quietly supplies a character, which is the failure every channel here has hit at least once.
ANIME_SUBJECTS = {
    "person": "a young woman standing at a kitchen counter, seen from the waist up, looking down at her hands",
    "interior": "a small tidy kitchen at dawn, empty, morning light across the counter and a kettle on the hob",
    "exterior": "an empty suburban street at dusk, parked cars, telephone poles, no people anywhere",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the channel style grid.")
    parser.add_argument("--guidance", type=float, help="override image.guidance_scale; sdxl only")
    parser.add_argument("--locked-only", action="store_true", help="draw the locked prefix and no candidates")
    parser.add_argument("--creatures", action="store_true", help="tune channel two: creature clauses and creature subjects")
    parser.add_argument("--anime", action="store_true", help="tune the anime channel: pin a medium the look can hold")
    options = parser.parse_args()

    config = load_channel_config()
    if options.guidance is not None:
        config = replace(config, guidance_scale=options.guidance)
    subjects = CREATURE_SUBJECTS if options.creatures else SUBJECTS
    if options.anime:
        subjects, styles = ANIME_SUBJECTS, dict(ANIME_CANDIDATES)
    elif options.creatures:
        styles = creature_styles(config.style_prefix)
    else:
        styles = {"current": config.style_prefix}
        if not options.locked_only:
            styles |= CANDIDATES

    folder = "anime" if options.anime else (f"creatures-{_grid_name(config)}" if options.creatures else _grid_name(config))
    output_dir = OUTPUT_ROOT / folder
    output_dir.mkdir(parents=True, exist_ok=True)
    legend = output_dir / "styles.txt"
    legend.write_text("".join(f"{name}: {prefix}\n" for name, prefix in styles.items()), encoding="utf-8")

    backend = backend_for(config)
    try:
        for style, prefix in styles.items():
            for offset, (subject, scene) in enumerate(subjects.items()):
                destination = output_dir / f"{style}--{subject}.png"
                # One seed per subject, shared by every style, so only the prefix varies between rows.
                backend.generate(f"{prefix} {scene}", config.negative_prompt, config.base_seed + offset, destination)
                print(destination.name, flush=True)
    finally:
        backend.close()

    print(f"\n{len(styles) * len(subjects)} images and {legend.name} in {output_dir}")


def _grid_name(config: ChannelConfig) -> str:
    """Guidance only bites on sdxl, so only its folders are split by the value."""
    if config.image_backend == SDXL:
        return f"guidance-{config.guidance_scale}"
    return config.image_backend


if __name__ == "__main__":
    main()
