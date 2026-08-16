"""Video assembly: one still per Scene, held for its Narration Clip plus the gap, hard cuts only."""

from __future__ import annotations

import subprocess
import wave
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import ChannelConfig
from .runs import RunStore
from .script import Script
from .subtitles import build_srt
from .tts import clip_duration_seconds

RENDER_STEPS = 3
MUSIC_SUFFIXES = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".oga", ".opus", ".aiff", ".aif", ".wma")

# The upload format, in one place: H.264 in yuv420p with AAC audio, ready to stream.
ENCODE = "-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -f mp4"


class RenderError(Exception):
    """The Video Package could not be assembled."""


@dataclass(frozen=True)
class Shot:
    """One Scene on screen: its still, and the whole frames it holds for."""

    image: Path
    frames: int


def render(
    runs: RunStore, run_id: str, script: Script, config: ChannelConfig, music: Path | None = None
) -> Iterator[str]:
    """Yields once per finished step, so a poll can tell subtitles from the long encode."""
    clips = [runs.narration_clip_path(run_id, scene.id) for scene in script.scenes]
    durations = [clip_duration_seconds(clip) for clip in clips]
    runs.save_subtitles(run_id, build_srt(script.scenes, durations, config.scene_gap_seconds))
    yield "subtitles"

    track = runs.narration_track_path(run_id)
    total_seconds = build_narration_track(clips, config.scene_gap_seconds, track)
    yield "narration"

    images = [runs.image_path(run_id, scene.id) for scene in script.scenes]
    shots = plan_shots(images, durations, config.scene_gap_seconds, config.fps)
    assemble(shots, track, total_seconds, config, runs.video_path(run_id), music)
    yield "video"


def plan_shots(images: Sequence[Path], durations: Sequence[float], gap_seconds: float, fps: int) -> list[Shot]:
    """Frames are counted off the running total, never per Scene, so rounding cannot drift a cut."""
    shots, spoken, allocated = [], 0.0, 0
    for image, duration in zip(images, durations):
        spoken += duration + gap_seconds
        boundary = round(spoken * fps)
        shots.append(Shot(image, boundary - allocated))
        allocated = boundary
    return shots


def missing_asset_error(runs: RunStore, run_id: str, script: Script) -> str | None:
    """Checked before the job starts, so a Run short of a Scene never becomes a broken video."""
    scenes = script.scenes
    shortfalls = [
        _shortfall(
            [scene.id for scene in scenes if not runs.narration_clip_path(run_id, scene.id).is_file()],
            "Narration Clip",
            "stickman_synthesize_narration",
        ),
        _shortfall(
            [scene.id for scene in scenes if not runs.image_path(run_id, scene.id).is_file()],
            "image",
            "stickman_generate_images with only_missing set",
        ),
    ]
    found = [shortfall for shortfall in shortfalls if shortfall]
    return " ".join(found) if found else None


def _shortfall(scene_ids: list[int], asset: str, remedy: str) -> str | None:
    if not scene_ids:
        return None
    listed = ", ".join(str(scene_id) for scene_id in scene_ids)
    subject = f"Scene {listed} has" if len(scene_ids) == 1 else f"Scenes {listed} have"
    return f"{subject} no {asset}; call {remedy}."


def music_tracks(config: ChannelConfig) -> list[str]:
    """Only the creator's own folder is ever offered, which is what keeps Content ID out of the way."""
    if not config.music_dir.is_dir():
        return []
    return sorted(track.name for track in config.music_dir.iterdir() if _is_track(track))


def music_path(config: ChannelConfig, track: str) -> Path:
    """A track is a name in the curated folder, never a path, so a Run cannot reach outside it."""
    chosen = config.music_dir / track
    if chosen.name != track or not chosen.exists():
        raise RenderError(f"no music track named '{track}'. {_folder_holds(config)}")
    if not _is_track(chosen):
        raise RenderError(
            f"'{track}' is in {config.music_dir} but is not one of the audio formats this pipeline "
            f"reads ({', '.join(MUSIC_SUFFIXES)}). Convert it and put the copy back in the folder."
        )
    return chosen


def _is_track(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MUSIC_SUFFIXES


def _folder_holds(config: ChannelConfig) -> str:
    available = music_tracks(config)
    if available:
        return f"{config.music_dir} holds: {', '.join(available)}."
    return f"{config.music_dir} holds no audio files yet; put the tracks you have cleared for use there."


def build_narration_track(clips: Sequence[Path], gap_seconds: float, destination: Path) -> float:
    """One silent gap after each clip, sample-accurate, so the length it returns is the video's length."""
    shape = _clip_shape(clips[0])
    channels, sample_width, rate = shape
    gap_frames = round(gap_seconds * rate)
    silence = b"\x00" * (gap_frames * channels * sample_width)
    frames = 0
    with wave.open(str(destination), "wb") as narration:
        narration.setnchannels(channels)
        narration.setsampwidth(sample_width)
        narration.setframerate(rate)
        for path in clips:
            if _clip_shape(path) != shape:
                raise RenderError(
                    f"{path.name} was recorded differently to {clips[0].name}, so joining them would "
                    "play one of them at the wrong speed. Delete the Run's audio folder and call "
                    "stickman_synthesize_narration to re-speak every Scene."
                )
            with wave.open(str(path), "rb") as clip:
                narration.writeframes(clip.readframes(clip.getnframes()))
                frames += clip.getnframes() + gap_frames
            narration.writeframes(silence)
    return frames / rate


def _clip_shape(path: Path) -> tuple[int, int, int]:
    with wave.open(str(path), "rb") as clip:
        return clip.getnchannels(), clip.getsampwidth(), clip.getframerate()


def assemble(
    shots: Sequence[Shot],
    track: Path,
    total_seconds: float,
    config: ChannelConfig,
    destination: Path,
    music: Path | None,
) -> None:
    """Publish by rename, so an interrupted encode never leaves a Run claiming a finished video."""
    partial = destination.with_name(destination.name + ".part")
    arguments = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error"]
    for shot in shots:
        held = f"{_held_seconds(shot.frames, config.fps):.6f}"
        arguments += ["-loop", "1", "-framerate", str(config.fps), "-t", held, "-i", str(shot.image)]
    arguments += ["-i", str(track)]
    graph = _stills(len(shots), config)
    if music is not None:
        arguments += ["-stream_loop", "-1", "-i", str(music)]
        graph += _music_mix(len(shots), config, total_seconds)
    arguments += ["-filter_complex", graph]
    arguments += ["-map", "[v]", "-map", "[a]" if music is not None else f"{len(shots)}:a"]
    arguments += ["-t", f"{total_seconds:.6f}", "-r", str(config.fps), *ENCODE.split(), str(partial)]
    _run(arguments)
    _publish(partial, destination)


def _held_seconds(frames: int, fps: int) -> float:
    """ffmpeg rounds -t to the nearest whole frame, ties to even, so only an exact multiple is safe."""
    return frames / fps


def _stills(count: int, config: ChannelConfig) -> str:
    """Every still is fitted then padded, never stretched, so a stray aspect ratio cannot distort a Scene."""
    size = f"{config.width}:{config.height}"
    chains = [
        f"[{position}:v]scale={size}:force_original_aspect_ratio=decrease,"
        f"pad={size}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,format=yuv420p[v{position}]"
        for position in range(count)
    ]
    joined = "".join(f"[v{position}]" for position in range(count))
    return ";".join(chains) + f";{joined}concat=n={count}:v=1:a=0[v]"


def _music_mix(count: int, config: ChannelConfig, total_seconds: float) -> str:
    """The bed is trimmed to the narration, so a long track cannot outlast the last spoken word."""
    return (
        f";[{count + 1}:a]volume={config.music_level_db}dB,atrim=duration={total_seconds:.6f}[bed]"
        f";[{count}:a][bed]amix=inputs=2:duration=first:normalize=0[a]"
    )


def _run(arguments: list[str]) -> None:
    try:
        result = subprocess.run(arguments, capture_output=True, text=True)
    except OSError as exc:
        raise RenderError(f"ffmpeg could not be started: {exc}. Install ffmpeg and put it on PATH.") from None
    if result.returncode != 0:
        raise RenderError(f"ffmpeg failed: {_last_line(result.stderr)}")


def _last_line(output: str) -> str:
    lines = output.strip().splitlines()
    return lines[-1].strip() if lines else "it gave no reason."


def _publish(partial: Path, destination: Path) -> None:
    """A player holding the previous video open blocks the swap on Windows, so say so and keep the render."""
    try:
        partial.replace(destination)
    except OSError as exc:
        raise RenderError(
            f"the new video could not replace {destination.name}: {exc.strerror}. Close anything "
            f"playing it and call stickman_render_video again; this render is kept as {partial.name}."
        ) from None
