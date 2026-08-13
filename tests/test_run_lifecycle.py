import json
from datetime import date
from typing import Any

from stickman_mcp.server import stickman_create_run, stickman_get_run, stickman_save_script

TOPIC = "How compound interest works"
SCRIPT: dict[str, Any] = {
    "topic": TOPIC,
    "title": "Compound Interest, Explained",
    "visual_bible": {"Ana": "a stickman with a short ponytail"},
    "scenes": [
        {"id": 1, "narration": "Money can earn money.", "image_prompt": "Ana holding a single coin"},
        {"id": 2, "narration": "Then that money earns too.", "image_prompt": "Ana beside a growing coin stack"},
    ],
}


def test_create_run_returns_dated_slug_id_and_prepares_scene_asset_folders(channel):
    response = json.loads(stickman_create_run("How compound interest works"))

    assert response["run_id"] == f"{date.today():%Y-%m-%d}-how-compound-interest-works"
    run_dir = channel.projects_dir / response["run_id"]
    assert (run_dir / "audio").is_dir()
    assert (run_dir / "images").is_dir()


def test_second_run_for_the_same_topic_today_gets_its_own_folder(channel):
    first = json.loads(stickman_create_run("How compound interest works"))["run_id"]
    second = json.loads(stickman_create_run("How compound interest works"))["run_id"]

    assert first != second
    assert (channel.projects_dir / first).is_dir()
    assert (channel.projects_dir / second).is_dir()


def test_saving_a_script_reports_the_scene_count_and_round_trips_on_disk(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    saved = json.loads(stickman_save_script(run_id, SCRIPT))

    assert saved["scene_count"] == 2
    stored = json.loads((channel.projects_dir / run_id / "script.json").read_text(encoding="utf-8"))
    assert stored["scenes"] == SCRIPT["scenes"]
    assert stored["title"] == SCRIPT["title"]
    assert stored["visual_bible"] == SCRIPT["visual_bible"]


def test_non_sequential_scene_ids_are_rejected_by_id_and_nothing_is_written(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    gapped = {**SCRIPT, "scenes": [SCRIPT["scenes"][0], {**SCRIPT["scenes"][1], "id": 3}]}

    response = stickman_save_script(run_id, gapped)

    assert response.startswith("Error:")
    assert "1, 3" in response
    assert "stickman_save_script" in response
    assert not (channel.projects_dir / run_id / "script.json").exists()


def _run_with_assets(channel) -> str:
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    (channel.projects_dir / run_id / "audio" / "001.wav").write_bytes(b"")
    (channel.projects_dir / run_id / "images" / "001.png").write_bytes(b"")
    return run_id


def test_editing_a_script_over_derived_assets_warns_and_names_the_remedy_tools(channel):
    run_id = _run_with_assets(channel)
    edited = _edit(scene=0, narration="Money can earn money, quietly.", image_prompt="Ana holding two coins")

    warning = json.loads(stickman_save_script(run_id, edited))["warning"]

    assert "stickman_synthesize_narration" in warning
    assert "stickman_generate_images" in warning


def test_editing_only_narration_leaves_the_images_alone(channel):
    run_id = _run_with_assets(channel)
    edited = _edit(scene=0, narration="Money can earn money, quietly.")

    warning = json.loads(stickman_save_script(run_id, edited))["warning"]

    assert "stickman_synthesize_narration" in warning
    assert "stickman_generate_images" not in warning


def test_resaving_an_unchanged_script_does_not_nag_about_good_assets(channel):
    run_id = _run_with_assets(channel)

    assert "warning" not in json.loads(stickman_save_script(run_id, SCRIPT))


def test_saving_a_first_script_carries_no_staleness_warning(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    assert "warning" not in json.loads(stickman_save_script(run_id, SCRIPT))


def _edit(scene: int, **changes: str) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = [dict(existing) for existing in SCRIPT["scenes"]]
    scenes[scene].update(changes)
    return {**SCRIPT, "scenes": scenes}


def test_run_status_tracks_whatever_is_on_disk(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    run_dir = channel.projects_dir / run_id

    fresh = json.loads(stickman_get_run(run_id))
    assert fresh["has_script"] is False
    assert fresh["scene_count"] == 0
    assert fresh["narration_clips"] == 0
    assert fresh["images"] == 0
    assert fresh["video_rendered"] is False

    stickman_save_script(run_id, SCRIPT)
    (run_dir / "audio" / "001.wav").write_bytes(b"")
    (run_dir / "images" / "001.png").write_bytes(b"")
    (run_dir / "images" / "002.png").write_bytes(b"")
    (run_dir / "video.mp4").write_bytes(b"")

    underway = json.loads(stickman_get_run(run_id))
    assert underway["has_script"] is True
    assert underway["scene_count"] == 2
    assert underway["narration_clips"] == 1
    assert underway["images"] == 2
    assert underway["video_rendered"] is True

    (run_dir / "images" / "002.png").unlink()
    assert json.loads(stickman_get_run(run_id))["images"] == 1


def test_status_of_a_corrupted_script_names_the_tool_that_replaces_it(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    (channel.projects_dir / run_id / "script.json").write_text('{"topic": ', encoding="utf-8")

    response = stickman_get_run(run_id)

    assert response.startswith("Error:")
    assert "stickman_save_script" in response


def test_status_of_an_unknown_run_names_the_tool_that_creates_one(channel):
    response = stickman_get_run("2026-01-01-never-created")

    assert response.startswith("Error:")
    assert "stickman_create_run" in response
