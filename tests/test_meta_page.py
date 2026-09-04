"""The page-interaction half of the Meta backend, driven against a local stub page.

Launches a real browser, so it is marked and excluded by default. It still never touches the
network: the stub is a file:// page and its picture arrives as a blob, exactly as Meta's does.

    uv run pytest -m browser
"""

from pathlib import Path

import pytest

from stickman_mcp.images import ImageError
from stickman_mcp.meta_ai import ask_for_image, refuse_if_blocked, start_thread

pytestmark = pytest.mark.browser

STUBS = Path(__file__).resolve().parent / "stubs"
TIMEOUT_SECONDS = 15.0


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        opened = browser.new_page()
        yield opened
        browser.close()


def _stub(page, name: str):
    page.goto((STUBS / name).as_uri())
    return page


def test_the_prompt_is_typed_into_the_composer_and_the_picture_comes_back(page):
    _stub(page, "meta-chat.html")

    data = ask_for_image(page, "Generate an image: a stickman waving", TIMEOUT_SECONDS)

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert page.locator(".asked").inner_text() == "Generate an image: a stickman waving"


def test_an_avatar_is_never_mistaken_for_the_answer(page):
    _stub(page, "meta-chat.html")

    data = ask_for_image(page, "a stickman waving", TIMEOUT_SECONDS)

    assert len(data) > 100, "the 24px avatar on the page must not have been picked up as the picture"


def test_a_page_asking_for_a_human_is_refused_before_anything_is_typed(page):
    _stub(page, "meta-blocked.html")

    with pytest.raises(ImageError) as caught:
        ask_for_image(page, "a stickman waving", TIMEOUT_SECONDS)

    assert "security check" in str(caught.value)
    assert page.locator(".asked").count() == 0


def test_a_healthy_chat_page_is_not_mistaken_for_a_block(page):
    _stub(page, "meta-chat.html")

    refuse_if_blocked(page)


def test_a_second_prompt_in_the_same_thread_still_finds_the_composer(page):
    """Meta grows a 'Conversation title' box after the first message; it is not the composer."""
    _stub(page, "meta-chat.html")

    first = ask_for_image(page, "scene one", TIMEOUT_SECONDS)
    second = ask_for_image(page, "scene two", TIMEOUT_SECONDS)

    assert first[:8] == b"\x89PNG\r\n\x1a\n" and second[:8] == b"\x89PNG\r\n\x1a\n"
    assert [asked.strip() for asked in page.locator(".asked").all_inner_texts()] == ["scene one", "scene two"]


def test_each_scene_starts_a_thread_of_its_own(page):
    """Meta refines the picture already in the thread instead of drawing the next prompt, so no Scene inherits one."""
    _stub(page, "meta-chat.html")
    ask_for_image(page, "scene one", TIMEOUT_SECONDS)

    start_thread(page, (STUBS / "meta-chat.html").as_uri())

    assert page.locator(".asked").count() == 0, "the previous Scene's thread must be gone"
    data = ask_for_image(page, "scene two", TIMEOUT_SECONDS)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert [asked.strip() for asked in page.locator(".asked").all_inner_texts()] == ["scene two"]


def test_a_prompt_about_a_security_check_is_not_mistaken_for_one(page):
    """The thread shows what we typed, so judging the page on our own words would ban us for a Scene."""
    _stub(page, "meta-chat.html")

    data = ask_for_image(page, "a stickman at an airport security check", TIMEOUT_SECONDS)

    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_block_that_arrives_mid_thread_is_still_caught(page):
    """Stripping our own words must not blind the check to Meta's."""
    _stub(page, "meta-chat.html")
    ask_for_image(page, "scene one", TIMEOUT_SECONDS)
    page.evaluate("() => document.body.insertAdjacentText('afterbegin', 'Please complete this security check')")

    with pytest.raises(ImageError) as caught:
        ask_for_image(page, "scene two", TIMEOUT_SECONDS)

    assert "security check" in str(caught.value)


def test_reference_pictures_are_attached_before_the_prompt_is_sent(page, tmp_path):
    _stub(page, "meta-chat.html")
    sheet = tmp_path / "lead.png"
    sheet.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    data = ask_for_image(page, "a woman walking", TIMEOUT_SECONDS, references=[sheet])

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert page.locator(".attached").inner_text() == "lead.png"


def test_two_references_go_up_together_because_a_scene_can_need_both(page, tmp_path):
    _stub(page, "meta-chat.html")
    sheet, setting = tmp_path / "lead.png", tmp_path / "001.png"
    for path in (sheet, setting):
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    ask_for_image(page, "a woman in the kitchen", TIMEOUT_SECONDS, references=[sheet, setting])

    assert page.locator(".attached").all_inner_texts() == ["lead.png", "001.png"]


def test_a_missing_reference_stops_the_scene_rather_than_drawing_without_it(page, tmp_path):
    _stub(page, "meta-chat.html")

    with pytest.raises(ImageError, match="reference picture"):
        ask_for_image(page, "a woman walking", TIMEOUT_SECONDS, references=[tmp_path / "gone.png"])
