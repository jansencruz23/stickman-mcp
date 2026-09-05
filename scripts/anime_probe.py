"""One-off: prove whether the anime channel is possible before its style is written.

Answers four questions on roughly eight images, hardest first, so a daily cap partway through
still leaves the decisive ones answered. Question 2 decides whether ADR-0003 is buildable.

Run with: STICKMAN_CHANNEL_CONFIG=channel-anime.toml uv run python scripts/anime_probe.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stickman_mcp.config import load_channel_config
from stickman_mcp.illustration import backend_for
from stickman_mcp.images import ImageError

OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "tuning" / "anime-probe"

SHEET = (
    "a character sheet of one young woman on a plain flat background, drawn four times in a row: "
    "front view, three quarter view, side view, and back view, all full body and the same height, "
    "with a second row of three head and shoulders drawings of her face, neutral then smiling then "
    "worried"
)
NEW_SETTING = "the same woman from the attached sheet standing at a bus stop in the rain, holding a paper bag"
ESTABLISHER = "a small kitchen at dawn, empty, morning light across the counter and a kettle on the hob"
BOTH = (
    "the woman from the attached character sheet standing in the kitchen from the attached photograph, "
    "pouring water from the kettle"
)
SHOT_SUBJECT = "a woman walking down a narrow city street between tall buildings"

# Most distinct first, and the ones most likely to fight the 16:9 clause: a wide shot is what every
# Establishing Shot is, and a close shot is the one that pulls Meta towards a portrait frame.
SHOT_ORDER = ("shot_wide", "shot_close", "shot_low", "shot_over_shoulder", "shot_high", "shot_medium")


# The setting reference failed on the first run, with two possible causes tangled together: the
# request said "do not edit or reproduce it", which is right for a character and wrong for a room,
# and the character sheet went up first. Two images separate them.
SETTING_ONLY = (
    "The attached picture is a drawing of a kitchen. Draw that same kitchen again - the same "
    "cabinets, the same colours, the same window in the same place, the same shelves - and put a "
    "young woman in it, standing at the stove pouring a kettle. Keep the room exactly as it is."
)
SETTING_FIRST = (
    "Two pictures are attached. The first is a drawing of a kitchen; the second is a character "
    "sheet of a young woman. Draw that same kitchen again, unchanged - the same cabinets, the same "
    "colours, the same window in the same place - with the woman from the character sheet standing "
    "at the stove pouring a kettle."
)


def setting_retest(config) -> None:
    """Talks to the chat directly: the point is to control the whole request, which compose_request owns."""
    from stickman_mcp.meta_ai import PlaywrightMetaChat, write_png

    kitchen = OUTPUT_ROOT / "3a-establisher.png"
    sheet = OUTPUT_ROOT / "1-sheet.png"
    if not kitchen.is_file() or not sheet.is_file():
        raise SystemExit(f"needs {kitchen.name} and {sheet.name} from the first run")

    plan = [
        ("5a-setting-only", SETTING_ONLY, [kitchen]),
        ("5b-setting-first", SETTING_FIRST, [kitchen, sheet]),
    ]
    chat = PlaywrightMetaChat(config.meta_profile_dir, config.meta_timeout_seconds)
    try:
        for index, (name, prompt, references) in enumerate(plan):
            destination = OUTPUT_ROOT / f"{name}.png"
            asked = f"{prompt} Avoid: {config.negative_prompt}."
            write_png(destination, chat.request_image(f"{config.style_prefix} {asked}", references))
            print(f"{destination.name}  ({index + 1} of {len(plan)})", flush=True)
    finally:
        chat.close()
    print(f"\n2 images in {OUTPUT_ROOT}. Compare both against 3a-establisher.png.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Meta AI for the anime channel.")
    parser.add_argument("--shots", type=int, default=4, help="how many shot clauses to test (0 skips stage 4)")
    parser.add_argument("--setting-retest", action="store_true", help="2 images: does a setting reference transfer?")
    options = parser.parse_args()

    if options.setting_retest:
        setting_retest(load_channel_config())
        return

    config = load_channel_config()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    shots = [name for name in SHOT_ORDER if name in config.clauses][: options.shots]

    sheet = OUTPUT_ROOT / "1-sheet.png"
    kitchen = OUTPUT_ROOT / "3a-establisher.png"
    plan: list[tuple[str, str, list[Path]]] = [
        ("1-sheet", SHEET, []),
        ("2-reference-or-edit", NEW_SETTING, [sheet]),
        ("3a-establisher", ESTABLISHER, []),
        ("3b-two-attachments", BOTH, [sheet, kitchen]),
    ]
    plan += [(f"4-{name}", f"{config.clauses[name]} {SHOT_SUBJECT}", []) for name in shots]

    _write_legend(len(plan), shots)
    backend = backend_for(config)
    drawn = 0
    try:
        for name, prompt, references in plan:
            destination = OUTPUT_ROOT / f"{name}.png"
            missing = [path.name for path in references if not path.is_file()]
            if missing:
                print(f"SKIP {name}: needs {', '.join(missing)}, which an earlier stage did not produce")
                continue
            backend.generate(
                f"{config.style_prefix} {prompt}", config.negative_prompt, config.base_seed + drawn, destination
            )
            drawn += 1
            print(f"{destination.name}  ({drawn} of {len(plan)})", flush=True)
    except ImageError as exc:
        print(f"\nSTOPPED after {drawn} image(s): {exc}")
    finally:
        backend.close()

    print(f"\n{drawn} image(s) in {OUTPUT_ROOT}. Read them against questions.txt.")


def _write_legend(total: int, shots: list[str]) -> None:
    (OUTPUT_ROOT / "questions.txt").write_text(
        "\n".join(
            [
                f"{total} images. What each one answers:",
                "",
                "1-sheet             Does Meta draw a usable multi-panel character sheet at all, in this style?",
                "2-reference-or-edit Attached the sheet, asked for a NEW scene. A new picture of the same woman",
                "                    is a pass; the sheet edited or returned is a fail, and the Lead needs",
                "                    rethinking.",
                "3a-establisher      An ordinary establishing shot. Also the second attachment for 3b.",
                "3b-two-attachments  THE DECIDING ONE. Sheet plus establisher together. If only one lands, the",
                "                    Lead-plus-setting design in ADR-0003 falls back to one picture plus text.",
                *[
                    f"4-{name:<16} Does this shot clause hold the style, or push Meta off it?"
                    for name in shots
                ],
                "",
                "Across all of them: does the anime look hold from one image to the next? That answer",
                "writes channel-anime.toml's style prefix and negative prompt, which are placeholders.",
                "",
                "Record what you find as comments in channel-anime.toml, beside what it explains.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
