"""The Meta AI backend, with the browser faked. Nothing here launches a browser or reaches the network."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import FakeMetaChat, MetaUnderFakeChat, finished, poll_job

from stickman_mcp import server
from stickman_mcp.config import ConfigError, load_channel_config
from stickman_mcp.images import ImageError, SDXLLightningBackend
from stickman_mcp.meta_ai import HOME_URL, LOGIN_HELP, MetaAIBackend, blocking_reason
from stickman_mcp.server import (
    stickman_create_run,
    stickman_generate_images,
    stickman_regenerate_image,
    stickman_save_script,
)


def test_a_channel_that_says_nothing_about_backends_still_draws_locally(channel):
    assert isinstance(server.image_backend(), SDXLLightningBackend)


def test_one_config_setting_switches_the_whole_pipeline_to_meta_ai(meta_channel):
    assert isinstance(server.image_backend(), MetaAIBackend)


def test_an_unknown_backend_name_names_the_ones_that_exist(tmp_path):
    source = tmp_path / "channel.toml"
    source.write_text(
        "[style]\nprefix = 'stickman,'\nnegative_prompt = 'photo'\n[image]\nbackend = 'dall-e'\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError) as caught:
        load_channel_config(source)

    assert "sdxl" in str(caught.value) and "meta-ai" in str(caught.value)


def test_the_picture_meta_answers_with_lands_at_the_destination(tmp_path):
    chat = FakeMetaChat()
    backend = MetaAIBackend(lambda: chat, delay_seconds=0.0, sleep=lambda _: None)
    destination = tmp_path / "images" / "001.png"
    destination.parent.mkdir()

    backend.generate("a stickman waving", "photo, watermark", 4243, destination)

    assert destination.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert "a stickman waving" in chat.prompts[0]


def test_the_negative_prompt_becomes_words_because_meta_offers_no_field_for_it(tmp_path):
    chat = FakeMetaChat()
    backend = MetaAIBackend(lambda: chat, delay_seconds=0.0, sleep=lambda _: None)

    backend.generate("stickman style, a coin", "photorealistic, watermark", 4243, tmp_path / "001.png")

    assert chat.prompts == ["Generate an image: stickman style, a coin. Avoid: photorealistic, watermark."]


def test_scenes_are_paced_by_the_configured_delay(tmp_path):
    slept: list[float] = []
    backend = MetaAIBackend(lambda: FakeMetaChat(), delay_seconds=8.0, sleep=slept.append)

    for scene in (1, 2, 3):
        backend.generate(f"scene {scene}", "", 4242 + scene, tmp_path / f"{scene:03d}.png")

    assert slept == [8.0, 8.0], "the delay falls between requests, so the first Scene waits for nothing"


def test_a_refused_request_is_never_asked_a_second_time(tmp_path):
    chat = FakeMetaChat()
    chat.raises = ImageError("Meta AI is showing a security check")
    backend = MetaAIBackend(lambda: chat, delay_seconds=0.0, sleep=lambda _: None)

    with pytest.raises(ImageError):
        backend.generate("scene 1", "", 4243, tmp_path / "001.png")

    assert len(chat.prompts) == 1, "retrying into a block is exactly what the ticket forbids"


@pytest.mark.parametrize(
    "url, visible, names",
    [
        ("https://www.facebook.com/login/?next=meta.ai", "Log into Facebook", "meta_login"),
        (HOME_URL, "Please complete this security check to continue", "security check"),
        (HOME_URL, "We limit how often you can do certain things. Try again later.", "limit"),
        (HOME_URL, "Your account has been temporarily restricted", "restricted"),
        (HOME_URL, "Ask Meta AI anything", None),
    ],
)
def test_whatever_meta_puts_in_the_way_is_named_rather_than_worked_around(url, visible, names):
    reason = blocking_reason(url, visible)

    if names is None:
        assert reason is None
    else:
        assert reason is not None and names in reason


SCRIPT = {
    "topic": "How compound interest works",
    "title": "Compound Interest, Explained",
    "scenes": [
        {"id": 1, "narration": "Money can earn money.", "image_prompt": "a single coin on a table"},
        {"id": 2, "narration": "That money earns too.", "image_prompt": "a growing stack of coins"},
    ],
}


@pytest.fixture
def meta_chat(monkeypatch):
    """The real backend at the tool surface with a fake browser behind it, so no browser starts."""
    chat = FakeMetaChat()
    monkeypatch.setattr(server, "image_backend", lambda: MetaAIBackend(lambda: chat, 0.0, lambda _: None))
    return chat


def _scripted_run(slug: str | None = None) -> str:
    run_id = json.loads(stickman_create_run(str(SCRIPT["topic"]), slug))["run_id"]
    stickman_save_script(run_id, SCRIPT)
    return run_id


@pytest.fixture
def meta_backend(monkeypatch):
    """The real backend behind the tools, so a batch proves what the browser session does."""
    backend = MetaUnderFakeChat()
    monkeypatch.setattr(server, "image_backend", lambda: backend)
    return backend


def test_every_scene_of_a_run_goes_down_a_single_chat_thread(meta_channel, meta_backend):
    run_id = _scripted_run()

    stickman_generate_images(run_id)
    poll_job(run_id, finished)

    assert len(meta_backend.chats) == 1, "a Run is one conversation, not one conversation per Scene"
    assert len(meta_backend.chats[0].prompts) == 2
    assert meta_backend.chats[0].closed, "the batch must shut its browser session when it ends"


def test_the_next_run_gets_its_own_thread_so_one_video_never_bleeds_into_the_next(meta_channel, meta_backend):
    for slug in ("first", "second"):
        run_id = _scripted_run(slug)
        stickman_generate_images(run_id)
        poll_job(run_id, finished)

    assert len(meta_backend.chats) == 2
    assert all(chat.closed for chat in meta_backend.chats)


def test_a_signed_out_profile_stops_the_job_and_says_how_to_sign_in(meta_channel, meta_chat):
    meta_chat.raises = ImageError(LOGIN_HELP)
    run_id = _scripted_run()

    stickman_generate_images(run_id)

    failed = poll_job(run_id, finished)
    assert failed["state"] == "error"
    assert "meta_login.py" in failed["error"]
    assert "password" in failed["error"]


def test_a_security_check_reaches_the_creator_through_the_regenerate_tool(meta_channel, meta_chat):
    meta_chat.raises = ImageError(str(blocking_reason(HOME_URL, "please complete this security check")))
    run_id = _scripted_run()

    response = stickman_regenerate_image(run_id, 1)

    assert response.startswith("Error:")
    assert "security check" in response


def test_a_rate_limited_account_is_reported_as_rate_limiting_not_as_a_crash(meta_channel, meta_chat):
    meta_chat.raises = ImageError(str(blocking_reason(HOME_URL, "we limit how often you can do this")))
    run_id = _scripted_run()

    stickman_generate_images(run_id)

    failed = poll_job(run_id, finished)
    assert failed["state"] == "error"
    assert "request_delay_seconds" in failed["error"]


def test_the_browser_profile_folder_the_shipped_config_names_is_gitignored(locked_channel):
    """The profile folder is the only place a Meta session ever lives, so it must never be committed."""
    ignored = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert f"{locked_channel.meta_profile_dir.name}/" in ignored


def test_the_shipped_channel_draws_with_meta_ai(locked_channel):
    """The creator switched this on 2026-08-20 after seeing real output. A channel decision, not an edit."""
    assert locked_channel.image_backend == "meta-ai"


def test_starting_the_server_never_pulls_a_browser_into_memory():
    """Playwright loads inside the methods that need it, so the default suite stays browser-free."""
    looked = subprocess.run(
        [sys.executable, "-c", "import sys, stickman_mcp.server; print('playwright' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert looked.stdout.strip() == "False"


def test_shutting_a_dead_browser_down_never_raises(tmp_path):
    """Close runs in a finally, so an error here would replace the message explaining why a job stopped."""

    class DeadChat(FakeMetaChat):
        def close(self) -> None:
            raise RuntimeError("the browser is already gone")

    backend = MetaAIBackend(lambda: DeadChat(), delay_seconds=0.0, sleep=lambda _: None)
    backend.generate("scene 1", "", 4243, tmp_path / "001.png")

    backend.close()


def test_the_delay_survives_the_browser_closing_between_redraws(tmp_path):
    """A redraw ends its session, but two requests in a row are a burst whether or not a batch made them."""
    slept: list[float] = []
    backend = MetaAIBackend(lambda: FakeMetaChat(), delay_seconds=8.0, sleep=slept.append)

    for scene in (1, 2):
        backend.generate(f"scene {scene}", "", 4242 + scene, tmp_path / f"{scene:03d}.png")
        backend.close()  # exactly what illustration.redraw_scene does

    assert slept == [8.0], "the second redraw must still wait, even in a fresh chat thread"


def test_the_delay_is_waited_out_before_the_browser_opens(tmp_path):
    """A window that appears and then sits idle for eight seconds reads as broken. Wait, then open."""
    events: list[str] = []

    def open_chat() -> FakeMetaChat:
        events.append("opened")
        return FakeMetaChat()

    backend = MetaAIBackend(open_chat, delay_seconds=8.0, sleep=lambda _: events.append("slept"))

    backend.generate("scene 1", "", 4243, tmp_path / "001.png")
    backend.close()
    backend.generate("scene 2", "", 4244, tmp_path / "002.png")

    assert events == ["opened", "slept", "opened"], "the second window must not open until the pause is over"
