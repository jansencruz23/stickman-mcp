"""One-off: read the same line in each candidate Kokoro voice, so the channel voice is picked by listening.

Run with: uv run python scripts/voice_audition.py
"""

from __future__ import annotations

from pathlib import Path

from stickman_mcp.config import load_channel_config
from stickman_mcp.tts import KokoroEngine, clip_duration_seconds

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "tuning" / "voice-audition"

# Written to swing: a flat opener, a turn, and a line that has to land, so a candidate is judged
# on delivery rather than timbre.
SAMPLE_LINE = (
    "He put in six hundred dollars and forgot about it. No plan, no second thought. "
    "Eleven years later he opened the account, and stopped. "
    "Eight thousand four hundred. From money he never missed."
)

# Kokoro's whole English roster. The 2026-08-16 audition heard eight of these; am_puck won a field
# that never included the warmer reads. Uncached voices download on first use.
CANDIDATES = [
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_heart",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
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
