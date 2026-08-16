"""One-off: read the same line in each candidate Kokoro voice, so the channel voice is picked by listening.

Run with: uv run python scripts/voice_audition.py
"""

from __future__ import annotations

from pathlib import Path

from stickman_mcp.config import load_channel_config
from stickman_mcp.tts import KokoroEngine, clip_duration_seconds

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tuning" / "voice-audition"

SAMPLE_LINE = (
    "Compound interest is the reason a small saving grows into a large one. "
    "Leave the money alone, and the interest starts earning interest of its own. "
    "Give it enough time, and the curve stops climbing and starts to bend."
)

CANDIDATES = [
    "af_heart",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "am_adam",
    "am_michael",
    "am_puck",
    "bf_emma",
]


def main() -> None:
    # Auditioning at the channel's own rate, so a candidate is judged as it would actually ship.
    speed = load_channel_config().voice_speed
    output_dir = OUTPUT_DIR / f"speed-{speed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = KokoroEngine()

    for voice in CANDIDATES:
        destination = output_dir / f"{voice}.wav"
        try:
            engine.synthesize(SAMPLE_LINE, voice, speed, destination)
        except Exception as exc:  # one unavailable voice must not cost the rest a reload
            print(f"{voice}: skipped, {exc}")
            continue
        print(f"{destination.name}  {clip_duration_seconds(destination):.1f}s")

    print(f"\nClips in {output_dir}")


if __name__ == "__main__":
    main()
