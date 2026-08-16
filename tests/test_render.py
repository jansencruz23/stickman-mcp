import json
import threading
import time
from typing import Any

import pytest
from conftest import (
    finished,
    first_frame,
    frame_colours,
    peak_dbfs,
    pixel,
    poll_job,
    probe_seconds,
    stream,
    write_solid_png,
    write_tone_wav,
)

from stickman_mcp.script import Scene
from stickman_mcp.server import (
    stickman_create_run,
    stickman_generate_images,
    stickman_get_run,
    stickman_list_music,
    stickman_render_video,
    stickman_save_metadata,
    stickman_save_script,
    stickman_synthesize_narration,
)
from stickman_mcp.subtitles import build_srt

TOPIC = "How compound interest works"
CLIP_SECONDS = {"Money can earn money.": 0.5, "That money earns too.": 0.3, "The curve bends upward.": 0.4}
SCRIPT: dict[str, Any] = {
    "topic": TOPIC,
    "title": "Compound Interest, Explained",
    "scenes": [
        {"id": position, "narration": narration, "image_prompt": f"picture {position}"}
        for position, narration in enumerate(CLIP_SECONDS, start=1)
    ],
}
TOTAL_SECONDS = sum(CLIP_SECONDS.values()) + len(CLIP_SECONDS) * 0.4  # one gap per Scene
DURATION_TOLERANCE = 0.35
INK = (0, 0, 0)
PAD = (255, 255, 255)


def _scenes(*narrations: str) -> list[Scene]:
    return [Scene(position, narration, "a picture") for position, narration in enumerate(narrations, start=1)]


def _run_ready_to_render(fake_tts, fake_images) -> str:
    """Every stage before rendering, driven through the tools exactly as the creator would."""
    fake_tts.seconds = dict(CLIP_SECONDS)
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    stickman_synthesize_narration(run_id)
    stickman_generate_images(run_id)
    poll_job(run_id, finished)
    return run_id


def test_each_cue_covers_its_own_clip_and_the_gap_falls_between_cues():
    scenes = _scenes("Money can earn money.", "That money earns too.")

    srt = build_srt(scenes, [8.975, 12.175], gap_seconds=0.4)

    assert srt == (
        "1\n"
        "00:00:00,000 --> 00:00:08,975\n"
        "Money can earn money.\n"
        "\n"
        "2\n"
        "00:00:09,375 --> 00:00:21,550\n"
        "That money earns too.\n"
        "\n"
    )


def test_cues_past_an_hour_roll_the_stamp_over_instead_of_counting_on_in_minutes():
    scenes = _scenes("The first hour ends here.", "The second hour starts here.")

    srt = build_srt(scenes, [3600.0, 61.5], gap_seconds=0.5)

    assert srt == (
        "1\n"
        "00:00:00,000 --> 01:00:00,000\n"
        "The first hour ends here.\n"
        "\n"
        "2\n"
        "01:00:00,500 --> 01:01:02,000\n"
        "The second hour starts here.\n"
        "\n"
    )


def test_a_topic_becomes_a_whole_video_package_without_leaving_the_tool_surface(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)  # create, save script, narrate, illustrate

    stickman_render_video(run_id)
    poll_job(run_id, finished)
    stickman_save_metadata(run_id, "Compound Interest, Explained", "Money that makes money.", ["finance"])

    status = json.loads(stickman_get_run(run_id))
    assert status["scene_count"] == status["narration_clips"] == status["images"] == 3
    assert (status["video_rendered"], status["subtitles"], status["metadata"]) == (True, True, True)
    assert status["job"]["state"] == "done"


def test_starting_a_render_hands_back_control_before_the_encode_has_finished(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    video = channel.projects_dir / run_id / "video.mp4"

    began = time.monotonic()
    started = json.loads(stickman_render_video(run_id))
    elapsed = time.monotonic() - began

    assert elapsed < 1.0, "starting a render must never approach the 30 s client tool timeout"
    assert (started["state"], started["done"], started["total"]) == ("running", 0, 3)
    assert not video.exists(), "the call returned only once ffmpeg had already written the video"
    assert poll_job(run_id, finished)["state"] == "done"
    assert video.is_file()


def test_the_video_lasts_every_narration_clip_plus_one_gap_per_scene(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)

    started = json.loads(stickman_render_video(run_id))

    assert (started["job"], started["state"]) == ("render", "running")
    assert poll_job(run_id, finished)["state"] == "done"
    video = channel.projects_dir / run_id / "video.mp4"
    assert abs(probe_seconds(video) - TOTAL_SECONDS) < DURATION_TOLERANCE


def test_the_video_is_the_1080p30_h264_upload_format_youtube_wants(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)

    stickman_render_video(run_id)
    poll_job(run_id, finished)

    video = channel.projects_dir / run_id / "video.mp4"
    picture = stream(video, "video")
    assert (picture["width"], picture["height"]) == (1920, 1080)
    assert (picture["codec_name"], picture["pix_fmt"], picture["avg_frame_rate"]) == ("h264", "yuv420p", "30/1")
    assert stream(video, "audio")["codec_name"] == "aac"


def test_the_subtitles_cue_every_scene_off_the_clips_that_were_actually_synthesized(
    channel, fake_tts, fake_images
):
    run_id = _run_ready_to_render(fake_tts, fake_images)

    stickman_render_video(run_id)
    poll_job(run_id, finished)

    subtitles = (channel.projects_dir / run_id / "subtitles.srt").read_bytes()
    assert subtitles == (
        b"1\n00:00:00,000 --> 00:00:00,500\nMoney can earn money.\n"
        b"\n"
        b"2\n00:00:00,900 --> 00:00:01,200\nThat money earns too.\n"
        b"\n"
        b"3\n00:00:01,600 --> 00:00:02,000\nThe curve bends upward.\n"
        b"\n"
    )


def test_a_scene_with_no_narration_clip_stops_the_render_and_names_the_tool_that_speaks_it(
    channel, fake_tts, fake_images
):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    (channel.projects_dir / run_id / "audio" / "002.wav").unlink()

    response = stickman_render_video(run_id)

    assert response.startswith("Error:")
    assert "Scene 2" in response
    assert "stickman_synthesize_narration" in response
    assert not (channel.projects_dir / run_id / "video.mp4").exists()


def test_a_scene_with_no_image_stops_the_render_and_names_the_tool_that_draws_it(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    (channel.projects_dir / run_id / "images" / "003.png").unlink()

    response = stickman_render_video(run_id)

    assert response.startswith("Error:")
    assert "Scene 3" in response
    assert "stickman_generate_images" in response
    assert not (channel.projects_dir / run_id / "video.mp4").exists()


def test_asking_to_render_while_the_images_are_still_drawing_points_at_the_running_job(
    channel, fake_tts, fake_images
):
    fake_images.pace = threading.Semaphore(0)  # hold the batch open, so most Scenes have no image yet
    fake_tts.seconds = dict(CLIP_SECONDS)
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    stickman_synthesize_narration(run_id)
    stickman_generate_images(run_id)

    response = stickman_render_video(run_id)

    assert response.startswith("Error:")
    assert "stickman_job_status" in response, "waiting is the remedy here, not starting another job"
    fake_images.pace.release(3)
    assert poll_job(run_id, finished)["state"] == "done"


def test_a_square_image_is_padded_into_the_frame_rather_than_stretched_across_it(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    for scene in SCRIPT["scenes"]:
        write_solid_png(channel.projects_dir / run_id / "images" / f"{scene['id']:03d}.png", 8, 8, INK)

    stickman_render_video(run_id)
    poll_job(run_id, finished)

    video = channel.projects_dir / run_id / "video.mp4"
    picture = stream(video, "video")
    assert (picture["width"], picture["height"]) == (1920, 1080)
    frame = first_frame(video)
    assert _close(pixel(frame, 960, 540), INK), "the square itself belongs in the middle of the frame"
    assert _close(pixel(frame, 20, 540), PAD), "a stretched square would have filled this column too"


def _close(found: tuple[int, int, int], expected: tuple[int, int, int]) -> bool:
    return all(abs(a - b) <= 20 for a, b in zip(found, expected))


# 0.517 s of speech plus the 0.4 s gap is 27.51 frames at 30 fps: a Scene that cannot land on a
# frame boundary, so any per-Scene rounding shows up as drift by the time the fifth Scene starts.
RAGGED_SECONDS = 0.517
RAGGED_SCENES = 5
SIGNAL_COLOURS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
HALF_A_FRAME = 1 / 60 + 1e-6  # the closest any cut can sit to a boundary that falls mid-frame


def test_no_cut_drifts_off_its_scene_however_ragged_the_clip_lengths_are(channel, fake_tts, fake_images):
    narrations = [f"Ragged scene number {position}." for position in range(1, RAGGED_SCENES + 1)]
    fake_tts.seconds = {narration: RAGGED_SECONDS for narration in narrations}
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(
        run_id,
        {
            "topic": TOPIC,
            "title": "Ragged",
            "scenes": [
                {"id": position, "narration": narration, "image_prompt": "a picture"}
                for position, narration in enumerate(narrations, start=1)
            ],
        },
    )
    stickman_synthesize_narration(run_id)
    for position, colour in enumerate(SIGNAL_COLOURS, start=1):
        write_solid_png(channel.projects_dir / run_id / "images" / f"{position:03d}.png", 16, 9, colour)

    stickman_render_video(run_id)
    poll_job(run_id, finished)

    scene = RAGGED_SECONDS + channel.scene_gap_seconds
    spoken = [position * scene for position in range(1, RAGGED_SCENES)]
    cuts = _cut_seconds(channel.projects_dir / run_id / "video.mp4")
    assert len(cuts) == RAGGED_SCENES - 1, f"expected one cut between each pair of Scenes, got {cuts}"
    for found, starts_speaking in zip(cuts, spoken):
        assert abs(found - starts_speaking) <= HALF_A_FRAME, f"cut at {found}s, Scene starts at {starts_speaking}s"


def _cut_seconds(video, fps: int = 30) -> list[float]:
    """Where the picture actually changes, classified by colour so the codec's noise cannot fake a cut."""
    shown = [min(SIGNAL_COLOURS, key=lambda c: sum(abs(a - b) for a, b in zip(colour, c))) for colour in frame_colours(video)]
    return [at / fps for at in range(1, len(shown)) if shown[at] != shown[at - 1]]


def _curate(channel, name: str, seconds: float = 0.6) -> None:
    channel.music_dir.mkdir(parents=True, exist_ok=True)
    write_tone_wav(channel.music_dir / name, seconds)


def test_the_music_list_holds_the_curated_tracks_and_nothing_else_in_the_folder(channel):
    _curate(channel, "calm-piano.wav")
    _curate(channel, "upbeat.wav")
    (channel.music_dir / "licence-notes.txt").write_text("bought from the audio library", encoding="utf-8")

    listed = json.loads(stickman_list_music())

    assert listed["tracks"] == ["calm-piano.wav", "upbeat.wav"]
    assert listed["music_dir"] == str(channel.music_dir)


def test_naming_a_track_the_folder_does_not_have_lists_the_ones_it_does(channel, fake_tts, fake_images):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    _curate(channel, "calm-piano.wav")

    response = stickman_render_video(run_id, music_track="epic-trailer.mp3")

    assert response.startswith("Error:")
    assert "calm-piano.wav" in response
    assert not (channel.projects_dir / run_id / "video.mp4").exists()


def test_a_short_track_loops_under_the_whole_narration_at_the_channels_quiet_level(
    channel, fake_tts, fake_images
):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    _curate(channel, "calm-piano.wav", seconds=0.6)  # a quarter of the narration, so it must repeat

    stickman_render_video(run_id, music_track="calm-piano.wav")
    poll_job(run_id, finished)

    video = channel.projects_dir / run_id / "video.mp4"
    assert abs(probe_seconds(video) - TOTAL_SECONDS) < DURATION_TOLERANCE
    assert peak_dbfs(video) == pytest.approx(channel.music_level_db, abs=1.5)
    assert peak_dbfs(video, from_seconds=1.5) == pytest.approx(channel.music_level_db, abs=1.5)


def test_a_track_longer_than_the_narration_is_trimmed_rather_than_extending_the_video(
    channel, fake_tts, fake_images
):
    run_id = _run_ready_to_render(fake_tts, fake_images)
    _curate(channel, "long-ambient.wav", seconds=TOTAL_SECONDS * 3)

    stickman_render_video(run_id, music_track="long-ambient.wav")
    poll_job(run_id, finished)

    video = channel.projects_dir / run_id / "video.mp4"
    assert abs(probe_seconds(video) - TOTAL_SECONDS) < DURATION_TOLERANCE


def test_upload_metadata_reads_back_with_the_title_description_and_tags_ready_to_paste(channel, fake_images):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)

    stickman_save_metadata(
        run_id,
        title="Compound Interest, Explained",
        description="Money that makes money, in three minutes.",
        tags=["finance", "compound interest", "explainer"],
    )

    saved = (channel.projects_dir / run_id / "metadata.txt").read_text(encoding="utf-8")
    assert "Compound Interest, Explained" in saved
    assert "Money that makes money, in three minutes." in saved
    assert "finance, compound interest, explainer" in saved
    assert json.loads(stickman_get_run(run_id))["metadata"] is True
