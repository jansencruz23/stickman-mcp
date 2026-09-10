"""Level a Run's Narration Clips up to 1.5x without clipping them.

A flat multiply is wrong: clips already peaking near full scale hard-clip. This raises each 10 ms
block by up to 1.5x but never past a 0.97 peak, smooths the per-block gains so the level does not
pump, and interpolates them across samples. Run once, after synthesis and before the render.

    python scripts/level_narration.py <run-audio-folder>
"""

import sys
import wave
from pathlib import Path

import numpy as np

MAX_GAIN = 1.5
CEILING = 0.97
BLOCK_SECONDS = 0.010
SMOOTH_SECONDS = 0.070
FULL_SCALE = 32768.0


def _block_gains(samples: np.ndarray, block: int) -> np.ndarray:
    """One gain per block: as much as 1.5x, less where the loudest sample in it would pass the ceiling."""
    blocks = np.array_split(samples, max(1, len(samples) // block))
    peaks = np.array([np.abs(b).max() if len(b) else 0.0 for b in blocks])
    headroom = np.where(peaks > 0, CEILING / np.maximum(peaks, 1e-9), MAX_GAIN)
    return np.minimum(MAX_GAIN, headroom)


def _smooth(gains: np.ndarray, window: int) -> np.ndarray:
    """A gain that jumps between neighbouring blocks is audible as pumping, so average across them."""
    if window < 2 or len(gains) < 2:
        return gains
    padded = np.pad(gains, (window // 2, window // 2), mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")[: len(gains)]


def level(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as source:
        params = source.getparams()
        raw = source.readframes(params.nframes)
    if params.sampwidth != 2:
        raise SystemExit(f"{path.name}: expected 16 bit audio, found {params.sampwidth * 8} bit")

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / FULL_SCALE
    block = max(1, int(params.framerate * BLOCK_SECONDS))
    gains = _smooth(_block_gains(samples, block), max(1, int(SMOOTH_SECONDS / BLOCK_SECONDS)))

    centres = np.arange(len(gains)) * block + block / 2
    per_sample = np.interp(np.arange(len(samples)), centres, gains)
    # Smoothing can lift a loud block above the headroom its own peak allowed, so hold every
    # individual sample under the ceiling as well as every block.
    per_sample = np.minimum(per_sample, CEILING / np.maximum(np.abs(samples), 1e-9))
    raised = np.clip(samples * per_sample, -1.0, 1.0)

    before = np.sqrt(np.mean(samples**2))
    after = np.sqrt(np.mean(raised**2))
    clipped = int(np.sum(np.abs(raised) >= 1.0))

    with wave.open(str(path), "wb") as sink:
        sink.setparams(params)
        sink.writeframes((raised * FULL_SCALE).astype(np.int16).tobytes())
    return (after / before if before > 0 else 1.0), clipped


def main() -> None:
    """Takes a folder, or individual clips when only a few Scenes were re-synthesized."""
    targets = [Path(argument) for argument in sys.argv[1:]]
    if not targets:
        raise SystemExit("usage: level_narration.py <audio-folder | clip.wav ...>")
    clips = sorted(targets[0].glob("*.wav")) if targets[0].is_dir() else targets
    if not clips:
        raise SystemExit(f"no clips in {targets[0]}")
    ratios, clipped = [], 0
    for clip in clips:
        ratio, count = level(clip)
        ratios.append(ratio)
        clipped += count
    print(f"levelled {len(clips)} clips")
    print(f"mean RMS gain {np.mean(ratios):.2f}x, worst {min(ratios):.2f}x, best {max(ratios):.2f}x")
    print(f"samples at full scale: {clipped}")


if __name__ == "__main__":
    main()
