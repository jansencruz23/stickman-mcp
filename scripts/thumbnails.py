"""Draw thumbnail candidates into a Run's own thumbnails/ folder.

Same backend and style prefix as the Scenes, with the card Scenes' text bans lifted so a thumbnail
may carry a word. Meta answers at whatever aspect it likes, so each PNG also gets a -1280.jpg
centre-cropped to 16:9 and then resized - resizing straight to 1280x720 squashes the picture.

    python scripts/thumbnails.py <run-id> [--channel channel-stikkky.toml]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)

# The channel has to be chosen before the config is read, and reading it is an import away.
_parser = argparse.ArgumentParser(description="Draw a Run's thumbnail candidates.")
_parser.add_argument("run_id")
_parser.add_argument("--channel", default="channel.toml", help="channel config to draw against")
_parser.add_argument("--style", help="replace the channel Style Prefix with a named one from STYLES")
_parser.add_argument("--set", dest="candidate_set", help="draw this candidate set instead of the run's own")
_options = _parser.parse_args()
os.environ["STICKMAN_CHANNEL_CONFIG"] = str(REPO / _options.channel)

from PIL import Image  # noqa: E402

from stickman_mcp.config import load_channel_config  # noqa: E402
from stickman_mcp.illustration import TEXT_BANS, backend_for, draw  # noqa: E402
from stickman_mcp.images import ImageError  # noqa: E402

# Measured 2026-09-08 against the two uploaded sets, which run 0-1.5 per cent click-through:
# both wasted a third or more of the frame on empty background, one stacked four words and cut the
# last off, and neither used a big numeral - the one thing the card Scenes prove Meta gets right.
# So every candidate here fills the frame, carries ONE word or ONE number and never both, and puts
# a face at readable size. plain_card rides on all of them because an invented meadow is the
# recorded failure of any Scene that should have no scenery.
# A candidate set may replace the channel Style Prefix outright. A thumbnail is the one image a
# viewer sees before clicking, so it is allowed to be drawn in a register the video never uses -
# a trade of retention for click-through, made deliberately and per set, never channel-wide.
STYLES: dict[str, str] = {
    "caricature": (
        "16:9 widescreen landscape frame, much wider than it is tall, detailed cartoon caricature "
        "illustration, bold heavy black outlines, strong cel shading, highly saturated colours, "
        "exaggerated features, dramatic lighting, high contrast, wide 16:9 landscape composition,"
    ),
}

# A replacement style needs its own bans: the channel list forbids the flat look's opposites, and
# "clean vector art", "smooth even line weight" and "cluttered background" are the very things a
# rendered caricature thumbnail wants.
NEGATIVES: dict[str, str] = {
    "caricature": (
        "photorealistic, photograph, 3d render, blurry, extra limbs, watermark, signature, "
        "portrait orientation, square image, tall narrow frame, flat colour, no shading, "
        "stick figure, simple line drawing"
    ),
}

CANDIDATES: dict[str, dict[str, str]] = {
    # The number in the title is the hook, so it is the number on the thumbnail. Faces stay wrecked
    # or astonished, never in pain: that is where Meta's refusal actually sits.
    "debt-caricature": {
        "eight-four": (
            "an extreme close up of one woman's face filling the left half of the frame, eyes wide "
            "and staring at the viewer, dark rings under them, mouth slightly open, and one enormous "
            "bold red 8400 dollar figure filling the entire right half of the frame, a dim kitchen "
            "behind her"
        ),
        "card-cut": (
            "an extreme close up of one woman's face filling the left third of the frame, eyes wide "
            "and staring, and an enormous credit card held up beside her face filling the rest of "
            "the frame, the card cracked clean across the middle, a dim kitchen behind her"
        ),
        "six-hundred": (
            "an extreme close up of one woman's face filling the left half of the frame, eyes wide "
            "and staring at the viewer, and the figure 600 in enormous bold red numerals filling the "
            "right half of the frame with a small red arrow beneath it pointing up to 8400"
        ),
    },
    "prehistoric-caricature": {
        "seconds": (
            "an extreme close up of one prehistoric man's face filling the left half of the frame, "
            "eyes bulging wide and bloodshot, mouth open in astonishment, matted hair and tangled "
            "beard, dirt on his skin, and the single word SECONDS in enormous bold red capitals "
            "filling the entire right half of the frame, a steaming volcanic landscape behind him"
        ),
        "jaws": (
            "an extreme close up of one prehistoric man's face filling the left third of the frame, "
            "eyes bulging wide and bloodshot, mouth open in astonishment, and an enormous "
            "tyrannosaurus head with its jaws wide open looming directly behind him filling the rest "
            "of the frame, a steaming volcanic landscape behind them both"
        ),
    },
    "ocean-caricature": {
        "helmet": (
            "an extreme close up of one deep sea diver's face inside a heavy brass diving helmet "
            "filling the left half of the frame, eyes bulging wide and bloodshot behind cracked "
            "glass, and one enormous bold red numeral 11 filling the entire right half of the frame, "
            "black deep ocean water behind him"
        ),
        "abyss": (
            "an extreme close up of one deep sea diver's face inside a heavy brass diving helmet "
            "filling the left half of the frame, eyes bulging wide and bloodshot, and an enormous "
            "anglerfish with a glowing lure and long teeth looming out of black water behind him "
            "filling the rest of the frame"
        ),
    },
    "evolution-caricature": {
        "ten": (
            "an extreme close up of one man's face filling the left half of the frame, eyes bulging "
            "wide and bloodshot, mouth open in astonishment, and one enormous bold red numeral 10 "
            "filling the entire right half of the frame, a dim natural history museum behind him"
        ),
        "crab": (
            "an extreme close up of one man's face filling the left third of the frame, eyes bulging "
            "wide and bloodshot, mouth open in astonishment, and an enormous crab with huge claws "
            "raised looming directly behind him filling the rest of the frame"
        ),
    },
    # Testing the reference thumbnail's register against Meta's recorded refusal of visible distress.
    # Levels rise: strain, then shouting, then the reference's own bloodied scream.
    "sleep-caricature": {
        "strain": (
            "an extreme close up of one exhausted man's face filling the left half of the frame, "
            "eyes bulging wide and bloodshot, deep dark hollow rings under both eyes, unshaven, "
            "pale sweating skin, staring straight at the viewer, and one enormous bold red numeral "
            "11 filling the entire right half of the frame, a dim bedroom behind him"
        ),
        "manic": (
            "an extreme close up of one man's face filling the left half of the frame, grinning too "
            "widely with his mouth open, eyes bulging and bloodshot with deep dark rings under them, "
            "hair wild and unwashed, and one enormous bold red numeral 11 filling the entire right "
            "half of the frame, a dim cluttered bedroom behind him"
        ),
        "split": (
            "two extreme close up cartoon faces of the same man side by side filling the frame, the "
            "left one calm and rested and smiling, the right one wild eyed and shouting with bulging "
            "bloodshot eyes and deep dark rings, the words DAY 1 in bold black capitals above the "
            "left face and DAY 11 above the right"
        ),
    },
    "2026-09-01-eleven-days-without-sleep": {
        "eleven": (
            "a single stick figure head seen front on filling the whole left half of the frame, "
            "enormous, eyes wide open and staring, huge dark grey rings under both eyes, flat "
            "mouthless expression, and one enormous rough red numeral 11 filling the entire right "
            "half of the frame from top to bottom"
        ),
        "wrecked": (
            "one single stick figure head seen front on filling almost the entire frame, drawn "
            "enormous and close, eyes wide open and staring straight ahead, huge dark grey rings "
            "under both eyes, hair sticking up in all directions, no other figure and nothing else "
            "in the frame"
        ),
        "day-eleven": (
            "one enormous rough red numeral 11 filling almost the entire frame from top to bottom, "
            "and one small stick figure head seen front on in the bottom left corner, eyes wide "
            "open and staring, dark grey rings under both eyes"
        ),
        "awake-word": (
            "a single stick figure head seen front on filling the whole left half of the frame, "
            "enormous, eyes wide open and staring, huge dark grey rings under both eyes, and the "
            "single word AWAKE in enormous rough red capitals filling the entire right half of the "
            "frame edge to edge"
        ),
    },
}


def crop_16_9(source: Path, destination: Path) -> tuple[int, int]:
    with Image.open(source) as image:
        picture = image.convert("RGB")
        width, height = picture.size
        target = width / height
        if target > 16 / 9:
            keep = int(height * 16 / 9)
            box = ((width - keep) // 2, 0, (width - keep) // 2 + keep, height)
        else:
            keep = int(width * 9 / 16)
            box = (0, (height - keep) // 2, width, (height - keep) // 2 + keep)
        picture.crop(box).resize((1280, 720), Image.Resampling.LANCZOS).save(destination, quality=90)
        return width, height


def main() -> None:
    run_id = _options.run_id
    candidates = CANDIDATES.get(_options.candidate_set or run_id)
    if candidates is None:
        sys.exit(f"no thumbnail candidates written for {run_id}; add a set to CANDIDATES first")

    config = load_channel_config()
    style = STYLES.get(_options.style, config.style_prefix) if _options.style else config.style_prefix
    folder = config.projects_dir / run_id / "thumbnails"
    folder.mkdir(parents=True, exist_ok=True)

    banned = NEGATIVES.get(_options.style or "", config.negative_prompt)
    negative = ", ".join(t.strip() for t in banned.split(",") if t.strip() not in TEXT_BANS)
    # A thumbnail is a card in every way that matters: words on it, and no scenery behind them.
    # The channel's anatomy clauses describe stick figures, so a replacement style drops them.
    clauses = "" if _options.style else " ".join(
        config.clauses[name] for name in ("people", "plain_card") if name in config.clauses
    )
    backend = backend_for(config)
    try:
        for offset, (name, subject) in enumerate(candidates.items()):
            png = folder / f"{name}.png"
            if png.exists():
                print(f"{name}: already drawn")
                continue
            try:
                draw(png, f"{style} {clauses} {subject}", negative, config.base_seed + offset, backend)
            except ImageError as exc:  # a refused candidate must not cost the ones after it
                print(f"{name}: REFUSED - {exc}", flush=True)
                continue
            size = crop_16_9(png, folder / f"{name}-1280.jpg")
            print(f"{name}: drew {size[0]}x{size[1]}, cropped to 1280x720", flush=True)
    finally:
        backend.close()
    print(f"thumbnails in {folder}")


if __name__ == "__main__":
    main()
