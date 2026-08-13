import json
from typing import Any

import pytest

from stickman_mcp.server import (
    stickman_create_run,
    stickman_get_run,
    stickman_save_script,
    stickman_synthesize_narration,
)

TOPIC = "How compound interest works"
FIRST = "Money can earn money."
SECOND = "Then that money earns too, and the curve bends upward."
SCRIPT: dict[str, Any] = {
    "topic": TOPIC,
    "title": "Compound Interest, Explained",
    "scenes": [
        {"id": 1, "narration": FIRST, "image_prompt": "Ana holding a single coin"},
        {"id": 2, "narration": SECOND, "image_prompt": "Ana beside a growing coin stack"},
    ],
}


def _scripted_run() -> str:
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    return run_id


def test_every_scene_gets_a_clip_named_by_its_padded_id_with_its_own_duration(channel, fake_tts):
    fake_tts.seconds = {FIRST: 1.5, SECOND: 2.25}
    run_id = _scripted_run()

    response = json.loads(stickman_synthesize_narration(run_id))

    clips = sorted(clip.name for clip in (channel.projects_dir / run_id / "audio").glob("*.wav"))
    assert clips == ["001.wav", "002.wav"]
    assert [scene["id"] for scene in response["scenes"]] == [1, 2]
    assert [scene["duration_seconds"] for scene in response["scenes"]] == pytest.approx([1.5, 2.25], abs=0.01)


def test_calling_again_speaks_nothing_and_still_reports_the_durations_on_disk(channel, fake_tts):
    fake_tts.seconds = {FIRST: 1.5, SECOND: 2.25}
    run_id = _scripted_run()
    first_response = json.loads(stickman_synthesize_narration(run_id))
    fake_tts.calls.clear()

    second_response = json.loads(stickman_synthesize_narration(run_id))

    assert fake_tts.calls == []
    assert second_response["scenes"] == first_response["scenes"]
    assert second_response["synthesized"] == 0
    assert second_response["skipped"] == 2


def test_a_deleted_clip_is_the_only_one_resynthesized(channel, fake_tts):
    run_id = _scripted_run()
    stickman_synthesize_narration(run_id)
    (channel.projects_dir / run_id / "audio" / "002.wav").unlink()
    fake_tts.calls.clear()

    response = json.loads(stickman_synthesize_narration(run_id))

    assert [text for text, _voice, _path in fake_tts.calls] == [SECOND]
    assert response["synthesized"] == 1
    assert response["skipped"] == 1


def test_run_status_counts_a_clip_for_every_scene_once_narration_finishes(channel, fake_tts):
    run_id = _scripted_run()

    stickman_synthesize_narration(run_id)

    status = json.loads(stickman_get_run(run_id))
    assert status["narration_clips"] == status["scene_count"] == 2


def test_total_duration_is_the_sum_of_the_scene_durations(channel, fake_tts):
    fake_tts.seconds = {FIRST: 1.5, SECOND: 2.25}
    run_id = _scripted_run()

    response = json.loads(stickman_synthesize_narration(run_id))

    assert response["total_duration_seconds"] == sum(
        scene["duration_seconds"] for scene in response["scenes"]
    )
    assert response["total_duration_seconds"] == pytest.approx(3.75, abs=0.01)


def test_narrating_a_run_without_a_script_names_the_tool_that_saves_one(channel, fake_tts):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    response = stickman_synthesize_narration(run_id)

    assert response.startswith("Error:")
    assert "stickman_save_script" in response
    assert fake_tts.calls == []


def test_an_engine_failure_is_reported_as_an_error_not_a_traceback(channel, fake_tts, monkeypatch):
    run_id = _scripted_run()

    def explode(text: str, voice: str, destination) -> None:
        raise RuntimeError("espeak-ng library not found")

    monkeypatch.setattr(fake_tts, "synthesize", explode)

    response = stickman_synthesize_narration(run_id)

    assert response.startswith("Error:")
    assert "espeak-ng library not found" in response
    assert "stickman_synthesize_narration" in response


def test_an_unreadable_clip_names_the_file_to_delete_instead_of_failing_forever(channel, fake_tts):
    run_id = _scripted_run()
    stickman_synthesize_narration(run_id)
    (channel.projects_dir / run_id / "audio" / "002.wav").write_bytes(b"not a wav at all")

    response = stickman_synthesize_narration(run_id)

    assert response.startswith("Error:")
    assert "002.wav" in response
    assert "delete" in response.lower()


def test_narrating_an_unknown_run_names_the_tool_that_creates_one(channel, fake_tts):
    response = stickman_synthesize_narration("2026-01-01-never-created")

    assert response.startswith("Error:")
    assert "stickman_create_run" in response
