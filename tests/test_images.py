import json
import threading
import time
from typing import Any

import pytest
from conftest import BACKEND_FAILURE, FakeImages, MetaUnderFakeChat, finished, poll_job

from stickman_mcp import server
from stickman_mcp.server import (
    stickman_create_run,
    stickman_generate_images,
    stickman_get_run,
    stickman_job_status,
    stickman_regenerate_image,
    stickman_save_script,
)


@pytest.fixture(params=["local", "meta-ai"])
def fake_images(request, monkeypatch):
    """Every criterion below is asserted against both backends, because the contract is the same one."""
    backend = FakeImages() if request.param == "local" else MetaUnderFakeChat()
    monkeypatch.setattr(server, "image_backend", lambda: backend)
    return backend


TOPIC = "How compound interest works"
SCRIPT: dict[str, Any] = {
    "topic": TOPIC,
    "title": "Compound Interest, Explained",
    "scenes": [
        {"id": 1, "narration": "Money can earn money.", "image_prompt": "a single coin on a table"},
        {"id": 2, "narration": "That money earns too.", "image_prompt": "a growing stack of coins"},
        {"id": 3, "narration": "The curve bends upward.", "image_prompt": "a curve bending upward"},
    ],
}


def _scripted_run() -> str:
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    return run_id


def test_every_scene_gets_an_image_named_by_its_padded_id(channel, fake_images):
    run_id = _scripted_run()

    started = json.loads(stickman_generate_images(run_id))

    assert started["total"] == 3
    assert poll_job(run_id, finished)["state"] == "done"
    images = sorted(image.name for image in (channel.projects_dir / run_id / "images").glob("*.png"))
    assert images == ["001.png", "002.png", "003.png"]
    assert json.loads(stickman_get_run(run_id))["images"] == 3


def test_the_job_starts_at_once_and_reports_a_rising_count_until_every_scene_is_drawn(channel, fake_images):
    fake_images.pace = threading.Semaphore(0)  # each image waits for the test to release it
    run_id = _scripted_run()

    began = time.monotonic()
    started = json.loads(stickman_generate_images(run_id))
    elapsed = time.monotonic() - began

    assert elapsed < 1.0, "starting a job must never approach the 30 s client tool timeout"
    assert started["run_id"] == run_id
    assert (started["job"], started["state"], started["done"], started["total"]) == ("images", "running", 0, 3)
    fake_images.pace.release(1)
    assert poll_job(run_id, lambda status: status["done"] == 1)["state"] == "running"
    fake_images.pace.release(2)
    complete = poll_job(run_id, finished)
    assert complete["state"] == "done"
    assert complete["done"] == complete["total"] == 3


def test_a_second_job_is_refused_while_the_first_is_still_drawing(channel, fake_images):
    fake_images.pace = threading.Semaphore(0)
    run_id = _scripted_run()
    stickman_generate_images(run_id)

    response = stickman_generate_images(run_id)

    assert response.startswith("Error:")
    assert "stickman_job_status" in response
    fake_images.pace.release(3)
    assert poll_job(run_id, finished)["done"] == 3
    assert len(fake_images.calls) == 3, "the refused call must not have drawn anything"


def test_a_backend_failure_ends_the_job_in_error_with_the_message_the_backend_gave(channel, fake_images):
    fake_images.fail_after = 1
    run_id = _scripted_run()

    stickman_generate_images(run_id)

    failed = poll_job(run_id, finished)
    assert failed["state"] == "error"
    assert BACKEND_FAILURE in failed["error"]
    assert "002.png" in failed["error"]
    assert "only_missing" in failed["resume"], "a failed job must name the way to finish it"
    assert failed["done"] == 1
    assert json.loads(stickman_get_run(run_id))["images"] == 1


def test_only_missing_draws_just_the_scenes_the_failed_job_never_reached(channel, fake_images):
    fake_images.fail_after = 1
    run_id = _scripted_run()
    stickman_generate_images(run_id)
    poll_job(run_id, finished)
    fake_images.fail_after = None
    fake_images.calls.clear()

    stickman_generate_images(run_id, only_missing=True)

    assert poll_job(run_id, finished)["state"] == "done"
    assert [call.seed for call in fake_images.calls] == [4244, 4245]
    assert json.loads(stickman_get_run(run_id))["images"] == 3


def test_the_server_applies_the_channel_style_and_a_seed_per_scene_to_every_prompt(channel, fake_images):
    run_id = _scripted_run()

    stickman_generate_images(run_id)
    poll_job(run_id, finished)

    for call, scene in zip(fake_images.calls, SCRIPT["scenes"]):
        assert call.prompt.startswith(channel.style_prefix)
        assert scene["image_prompt"] in call.prompt
        assert call.negative_prompt == channel.negative_prompt
    assert [call.seed for call in fake_images.calls] == [4243, 4244, 4245]  # base_seed 4242 plus scene id


def test_regenerating_a_scene_draws_it_in_the_locked_channel_style(locked_channel, fake_images):
    """Reads the shipped config, so this fails if the tuned Style Prefix stops reaching the backend."""
    run_id = _scripted_run()

    stickman_regenerate_image(run_id, 2)

    call = fake_images.calls[-1]
    assert call.prompt == f"{locked_channel.style_prefix} {SCRIPT['scenes'][1]['image_prompt']}"
    assert call.negative_prompt == locked_channel.negative_prompt


def _batch(run_id: str) -> None:
    stickman_generate_images(run_id)
    poll_job(run_id, finished)


def test_regenerating_without_a_seed_rerolls_into_a_different_image(channel, fake_images):
    run_id = _scripted_run()
    _batch(run_id)
    image = channel.projects_dir / run_id / "images" / "002.png"
    from_batch = image.read_bytes()

    response = json.loads(stickman_regenerate_image(run_id, 2))

    assert response["seed"] != 4244
    assert image.read_bytes() != from_batch


def test_regenerating_with_the_batch_seed_reproduces_the_batch_image_exactly(channel, fake_images):
    if not fake_images.honours_seeds:
        pytest.skip("Meta AI accepts no seed, so only a local backend can promise the same pixels twice")
    run_id = _scripted_run()
    _batch(run_id)
    image = channel.projects_dir / run_id / "images" / "002.png"
    from_batch = image.read_bytes()
    stickman_regenerate_image(run_id, 2)

    stickman_regenerate_image(run_id, 2, seed=4244)

    assert image.read_bytes() == from_batch


def test_a_replacement_prompt_reaches_the_saved_script_before_it_reaches_the_backend(
    channel, fake_images, monkeypatch
):
    run_id = _scripted_run()
    _batch(run_id)
    script_file = channel.projects_dir / run_id / "script.json"
    fake_images.calls.clear()
    drawn_against: list[str] = []
    generate = fake_images.generate

    def record_the_script_the_backend_drew_against(*args, **kwargs):
        drawn_against.append(script_file.read_text(encoding="utf-8"))
        generate(*args, **kwargs)

    monkeypatch.setattr(fake_images, "generate", record_the_script_the_backend_drew_against)

    stickman_regenerate_image(run_id, 2, image_prompt="a beanstalk made of coins")

    assert "a beanstalk made of coins" in drawn_against[0], "the Script must be saved before drawing"
    saved = json.loads(script_file.read_text(encoding="utf-8"))
    assert saved["scenes"][1]["image_prompt"] == "a beanstalk made of coins"
    assert saved["scenes"][0]["image_prompt"] == SCRIPT["scenes"][0]["image_prompt"]
    assert "a beanstalk made of coins" in fake_images.calls[0].prompt


def test_regenerating_a_scene_the_script_does_not_have_names_the_range(channel, fake_images):
    run_id = _scripted_run()

    response = stickman_regenerate_image(run_id, 7)

    assert response.startswith("Error:")
    assert "1 to 3" in response
    assert fake_images.calls == []


def test_illustrating_a_run_without_a_script_names_the_tool_that_saves_one(channel, fake_images):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    response = stickman_generate_images(run_id)

    assert response.startswith("Error:")
    assert "stickman_save_script" in response
    assert fake_images.calls == []


def test_asking_for_job_status_before_any_job_names_the_tool_that_starts_one(channel, fake_images):
    run_id = _scripted_run()

    response = stickman_job_status(run_id)

    assert response.startswith("Error:")
    assert "stickman_generate_images" in response


def test_job_status_of_an_unknown_run_names_the_tool_that_creates_one(channel, fake_images):
    response = stickman_job_status("2026-01-01-never-created")

    assert response.startswith("Error:")
    assert "stickman_create_run" in response


def test_a_job_left_running_by_a_stopped_server_is_reported_as_failed_not_forever_running(channel, fake_images):
    run_id = _scripted_run()
    _batch(run_id)
    job_file = channel.projects_dir / run_id / "job.json"
    stopped = {**json.loads(job_file.read_text(encoding="utf-8")), "state": "running", "done": 1}
    job_file.write_text(json.dumps(stopped), encoding="utf-8")  # as a killed server would leave it

    status = json.loads(stickman_job_status(run_id))

    assert status["state"] == "error"
    assert "only_missing" in status["error"]
    assert json.loads(stickman_generate_images(run_id, only_missing=True))["state"] == "running"


def test_run_status_carries_the_job_so_one_call_answers_where_am_i(channel, fake_images):
    run_id = _scripted_run()
    assert "job" not in json.loads(stickman_get_run(run_id))

    _batch(run_id)

    status = json.loads(stickman_get_run(run_id))
    assert status["job"]["state"] == "done"
    assert status["job"]["done"] == status["images"] == 3


def test_a_card_scene_is_the_one_place_words_are_allowed(locked_channel):
    """A ranking screen exists to be read, so the text bans lift for it and nothing else does."""
    from stickman_mcp.illustration import negative_for
    from stickman_mcp.script import Scene

    ordinary = negative_for(Scene(1, "n", "p"), locked_channel)
    card = negative_for(Scene(1, "n", "p", card=True), locked_channel)

    assert "text" in ordinary.split(", ") and "text" not in card.split(", ")
    assert "watermark" not in card.split(", ") and "signature" not in card.split(", ")
    assert "photorealistic" in card, "a card is still the channel's look, not a free-for-all"
    assert "stick figure animals" in card


def test_a_clause_rides_only_on_the_scenes_that_ask_for_it(locked_channel):
    """Meta supplies whatever the prefix names, so an unmarked Scene must not carry a subject clause."""
    from dataclasses import replace

    from stickman_mcp.illustration import prefix_for
    from stickman_mcp.script import Scene

    creature = "any creature is drawn as a solid filled cartoon animal,"
    channel = replace(locked_channel, clauses={"creature": creature})

    assert prefix_for(Scene(1, "n", "p", clauses=("creature",)), channel).endswith(creature)
    assert prefix_for(Scene(1, "n", "p"), channel) == channel.style_prefix
    assert prefix_for(Scene(1, "n", "p", card=True), channel) == channel.style_prefix


def test_a_scene_naming_a_clause_the_channel_lacks_says_so(locked_channel):
    """A typo must stop the batch by name rather than quietly drawing 86 Scenes without the rule."""
    from dataclasses import replace

    from stickman_mcp.illustration import prefix_for
    from stickman_mcp.script import Scene, ScriptError

    channel = replace(locked_channel, clauses={"creature": "any creature is solid,"})
    with pytest.raises(ScriptError) as failure:
        prefix_for(Scene(4, "n", "p", clauses=("creatures",)), channel)
    assert "creatures" in str(failure.value) and "creature" in str(failure.value)


def test_a_channel_without_clauses_is_untouched(locked_channel):
    """A channel may state its whole look in the prefix, and then every Scene gets exactly that."""
    from dataclasses import replace

    from stickman_mcp.illustration import prefix_for
    from stickman_mcp.script import Scene

    channel = replace(locked_channel, clauses={})
    for scene in (Scene(1, "n", "p"), Scene(1, "n", "p", card=True)):
        assert prefix_for(scene, channel) == channel.style_prefix
