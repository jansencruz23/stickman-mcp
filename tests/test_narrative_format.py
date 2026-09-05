"""The Format a Run declares, and the Lead sheet that rides with the Scenes that opted in."""

import json

import pytest
from conftest import FakeImages, finished, poll_job, write_tiny_png

from stickman_mcp import server
from stickman_mcp.script import ScriptError, parse_script
from stickman_mcp.server import (
    stickman_audition_lead,
    stickman_choose_lead,
    stickman_create_run,
    stickman_generate_images,
    stickman_get_run,
    stickman_regenerate_image,
    stickman_save_script,
)

TOPIC = "Life before AI"


@pytest.fixture
def story_backend(channel, monkeypatch):
    """The image backend swapped out at the tool surface; tests read its call log back."""
    backend = FakeImages()
    monkeypatch.setattr(server, "image_backend", lambda: backend)
    return backend


@pytest.fixture
def drawn_story(story_backend):
    """A saved narrative Run with every Scene already drawn, which is where a Checkpoint finds it."""
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, _story())
    stickman_generate_images(run_id)
    poll_job(run_id, finished)
    return run_id


def _story(**overrides):
    script = {
        "topic": TOPIC,
        "title": "Life Before AI",
        "format": "narrative",
        "scenes": [
            {"id": 1, "narration": "A kitchen at dawn.", "image_prompt": "a kitchen at dawn"},
            {"id": 2, "narration": "She reaches for a pen.", "image_prompt": "a hand takes a pen", "lead": True},
            {"id": 3, "narration": "She writes it down.", "image_prompt": "writing on paper", "lead": True},
            {"id": 4, "narration": "Outside, a street.", "image_prompt": "a wide street"},
            {"id": 5, "narration": "She walks to work.", "image_prompt": "walking past shops", "lead": True},
        ],
    }
    return script | overrides


def test_format_defaults_to_illustrative_so_every_existing_script_still_parses():
    script = parse_script(
        {
            "topic": TOPIC,
            "title": "A List",
            "scenes": [{"id": 1, "narration": "One thing.", "image_prompt": "one thing"}],
        }
    )

    assert script.format == "illustrative"


def test_an_unknown_format_is_refused_by_name():
    with pytest.raises(ScriptError, match="script.format must be one of illustrative, narrative"):
        parse_script(_story(format="cinematic"))


def test_an_illustrative_script_may_still_carry_a_lead():
    script = parse_script(
        {
            "topic": TOPIC,
            "title": "A List",
            "scenes": [{"id": 1, "narration": "One.", "image_prompt": "one", "lead": True}],
        }
    )

    assert script.scenes[0].lead is True


def test_a_saved_narrative_script_round_trips_its_format_and_scene_flags(channel):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    stickman_save_script(run_id, _story())

    saved = json.loads((channel.projects_dir / run_id / "script.json").read_text(encoding="utf-8"))
    assert saved["format"] == "narrative"
    assert saved["scenes"][1]["lead"] is True
    assert "lead" not in saved["scenes"][0], "a flag stays off the Scenes that never set it"


def test_replacing_an_image_prompt_keeps_the_scene_flags_it_already_had(channel, drawn_story):
    run_id = drawn_story

    stickman_regenerate_image(run_id, 2, image_prompt="a hand takes a fountain pen")

    saved = json.loads((channel.projects_dir / run_id / "script.json").read_text(encoding="utf-8"))
    assert saved["scenes"][1]["lead"] is True, "a rewritten prompt must not strip the Scene's flags"


def test_regenerating_an_ordinary_scene_warns_about_nothing(drawn_story):
    result = json.loads(stickman_regenerate_image(drawn_story, 3))

    assert "warning" not in result


def _drawn(backend, scene_id: int):
    """The one call that drew this Scene. Images publish by rename, so the backend sees the .part name."""
    return next(call for call in backend.calls if call.destination.name.startswith(f"{scene_id:03d}.png"))


def _run_with_lead(channel, has_lead: bool = True) -> str:
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(run_id, _story())
    if has_lead:
        write_tiny_png(channel.projects_dir / run_id / "reference" / "lead.png", 7)
    return run_id


def test_the_lead_sheet_rides_only_on_the_scenes_that_are_marked_for_it(channel, story_backend):
    run_id = _run_with_lead(channel)

    stickman_generate_images(run_id)
    poll_job(run_id, finished)

    lead_sheet = channel.projects_dir / run_id / "reference" / "lead.png"
    assert lead_sheet in _drawn(story_backend, 2).references
    assert lead_sheet in _drawn(story_backend, 5).references
    assert _drawn(story_backend, 1).references == (), "a Scene nobody marked attaches nothing at all"
    assert _drawn(story_backend, 4).references == ()


def test_a_marked_scene_draws_without_the_lead_when_no_sheet_was_ever_chosen(channel, story_backend):
    run_id = _run_with_lead(channel, has_lead=False)

    stickman_generate_images(run_id)
    poll_job(run_id, finished)

    assert _drawn(story_backend, 2).references == (), "a marked Scene with no sheet yet draws plainly"


def test_an_illustrative_run_attaches_nothing_even_when_a_scene_claims_the_lead(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_save_script(
        run_id,
        {
            "topic": TOPIC,
            "title": "A List",
            "scenes": [
                {"id": 1, "narration": "One.", "image_prompt": "one"},
                {"id": 2, "narration": "Two.", "image_prompt": "two"},
            ],
        },
    )

    stickman_generate_images(run_id)
    poll_job(run_id, finished)

    assert all(call.references == () for call in story_backend.calls), "no format change, no new behaviour"


def test_the_audition_draws_the_candidates_it_was_asked_for_into_the_reference_folder(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    started = json.loads(stickman_audition_lead(run_id, "a character sheet of a woman, four angles", 3))
    poll_job(run_id, finished)

    assert (started["job"], started["total"]) == ("lead", 3)
    drawn = sorted(path.name for path in (channel.projects_dir / run_id / "reference").glob("*.png"))
    assert drawn == ["lead-01.png", "lead-02.png", "lead-03.png"]
    assert json.loads(stickman_get_run(run_id))["lead_chosen"] is False


def test_the_audition_carries_the_style_prefix_like_any_other_image(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    stickman_audition_lead(run_id, "a character sheet of a woman", 1)
    poll_job(run_id, finished)

    assert story_backend.calls[0].prompt.startswith(channel.style_prefix)


def test_choosing_a_candidate_keeps_it_as_the_lead_without_removing_the_others(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_audition_lead(run_id, "a character sheet of a woman", 2)
    poll_job(run_id, finished)
    reference = channel.projects_dir / run_id / "reference"

    chosen = json.loads(stickman_choose_lead(run_id, 2))

    assert chosen["candidate"] == 2
    assert (reference / "lead.png").read_bytes() == (reference / "lead-02.png").read_bytes()
    assert (reference / "lead-01.png").is_file(), "the candidates stay, so the creator can change their mind"
    assert json.loads(stickman_get_run(run_id))["lead_chosen"] is True


def test_choosing_a_candidate_that_was_never_drawn_says_which_ones_were(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]
    stickman_audition_lead(run_id, "a character sheet of a woman", 2)
    poll_job(run_id, finished)

    result = stickman_choose_lead(run_id, 7)

    assert result.startswith("Error:")
    assert "lead-01.png, lead-02.png" in result


def test_an_audition_of_an_absurd_size_is_refused_before_it_spends_the_daily_allowance(channel, story_backend):
    run_id = json.loads(stickman_create_run(TOPIC))["run_id"]

    result = stickman_audition_lead(run_id, "a character sheet", 40)

    assert result.startswith("Error:")
    assert story_backend.calls == [], "nothing may be drawn when the request is refused"


