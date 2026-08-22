"""Meta AI as an image backend: one logged-in browser, a fresh chat thread per Scene."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from .images import ImageError

HOME_URL = "https://www.meta.ai/"
IMAGE_REQUEST = "Generate an image:"

LOGIN_HELP = (
    "Meta AI is not logged in. Run 'uv run python scripts/meta_login.py' and sign in by hand once, "
    "then start this job again. The server never handles your password."
)
HUMAN_CHECK = "Meta AI is showing a security check or CAPTCHA. Finish it by hand in the browser."
IDENTITY = "Meta AI is asking you to confirm your identity. Deal with it by hand in the browser."
CHECKPOINT = "Meta put a checkpoint on the account. Clear it by hand in the browser before running again."
RATE_LIMIT = "Meta is rate limiting the account. Raise meta_ai.request_delay_seconds and try again later."

# Meta's own words on the left, what the creator should do about them on the right.
BLOCKERS: tuple[tuple[str, str], ...] = (
    ("security check", HUMAN_CHECK),
    ("captcha", HUMAN_CHECK),
    ("confirm your identity", IDENTITY),
    ("checkpoint", CHECKPOINT),
    ("temporarily restricted", "Meta has temporarily restricted this account. Wait it out or use local SDXL."),
    ("temporarily blocked", "Meta has temporarily blocked this account. Wait it out or use local SDXL."),
    ("we limit how often", RATE_LIMIT),
    ("try again later", RATE_LIMIT),
)

LOGIN_SIGNS = ("log into facebook", "log in to facebook", "continue with facebook", "create new account")


class MetaChat(Protocol):
    """One open Meta AI session. It knows the page; it knows nothing about Runs or Scenes."""

    def request_image(self, prompt: str) -> bytes:
        """Send one prompt down the thread and return the image Meta answered with."""

    def close(self) -> None:
        """Shut the thread and the browser behind it down."""


class MetaAIBackend:
    """Sequential requests, each down a thread of its own. Meta takes a sentence, not a seed."""

    def __init__(
        self,
        open_chat: Callable[[], MetaChat],
        delay_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.open_chat = open_chat
        self.delay_seconds = delay_seconds
        self.sleep = sleep
        self._chat: MetaChat | None = None
        self._asked = False

    def generate(self, prompt: str, negative_prompt: str, seed: int, destination: Path) -> None:
        """The seed is accepted and unused: Meta offers no way to ask for the same pixels twice."""
        self._pace()  # waited out before the window appears, so an open browser is always a busy one
        chat = self._opened()
        write_png(destination, chat.request_image(compose_request(prompt, negative_prompt)))

    def close(self) -> None:
        """Called when a batch or a redraw ends, which is what keeps a Run to exactly one browser."""
        chat, self._chat = self._chat, None
        if chat is not None:
            with suppress(Exception):  # teardown must never replace the failure that caused it
                chat.close()

    def _opened(self) -> MetaChat:
        if self._chat is None:
            self._chat = self.open_chat()
        return self._chat

    def _pace(self) -> None:
        """Outlives the chat on purpose: back-to-back redraws are a burst as surely as a batch is."""
        if self._asked:
            self.sleep(self.delay_seconds)
        self._asked = True


def blocking_reason(url: str, visible_text: str) -> str | None:
    """Reads the page the way a person would, so a block is reported and never evaded."""
    seen = visible_text.lower()
    if "/login" in url or "checkpoint" in url or any(sign in seen for sign in LOGIN_SIGNS):
        return LOGIN_HELP
    for phrase, reason in BLOCKERS:
        if phrase in seen:
            return reason
    return None


def compose_request(prompt: str, negative_prompt: str) -> str:
    """Meta reads one plain sentence, so the negative prompt has to become words rather than a field."""
    asked = f"{IMAGE_REQUEST} {prompt}"
    if not negative_prompt.strip():
        return asked
    return f"{asked}. Avoid: {negative_prompt}."


def write_png(destination: Path, data: bytes) -> None:
    """Meta answers in whatever format it likes, but the pipeline promised ffmpeg a PNG."""
    try:
        picture = Image.open(BytesIO(data))
        picture.convert("RGB").save(destination, format="PNG")
    except OSError as exc:
        raise ImageError(f"Meta AI returned {len(data)} bytes that are not a readable image: {exc}") from None


# --- Everything below knows Meta's page structure, so a UI change is a one-file fix. ---

MIN_IMAGE_PIXELS = 256  # avatars, icons and emoji are small; a generated picture is not
COMPOSER = '[data-testid="composer-input"][contenteditable="true"]'
POLL_SECONDS = 0.25
SETTLE_SECONDS = 1.5
LAST_CHARACTERS = 200

BIG_IMAGES = """
(minimum) => Array.from(document.images)
  .filter((picture) => picture.complete && picture.naturalWidth >= minimum)
  .map((picture) => picture.src)
"""

FETCH_AS_BASE64 = """
async (src) => {
  const response = await fetch(src);
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
"""


def refuse_if_blocked(page: Any, sent: Sequence[str] = ()) -> None:
    """Judges Meta's words, not ours, or a Scene about a security check would read as a security check."""
    visible = page.inner_text("body")
    for prompt in sent:
        visible = visible.replace(prompt, "")
    reason = blocking_reason(page.url, visible)
    if reason is not None:
        raise ImageError(reason)


def start_thread(page: Any, home_url: str = HOME_URL) -> None:
    """A Scene never inherits a thread: with a picture already in one, Meta refines it instead of drawing."""
    page.goto(home_url)
    page.wait_for_selector(COMPOSER)


def ask_for_image(page: Any, prompt: str, timeout_seconds: float, sent: Sequence[str] = ()) -> bytes:
    """One prompt into the composer, then wait for the picture, the way a person uses the page."""
    asked = [*sent, prompt]
    refuse_if_blocked(page, asked)
    already = big_images(page)
    box = composer(page)
    box.fill(prompt)  # fill focuses without a pointer hit test, which anything overlapping would fail
    box.press("Enter")
    return download(page, wait_for_picture(page, already, timeout_seconds, asked))


def composer(page: Any) -> Any:
    """Meta puts its testid on a hidden textarea too, and only the real composer is ever editable."""
    return page.locator(COMPOSER)


def big_images(page: Any) -> list[str]:
    return list(page.evaluate(BIG_IMAGES, MIN_IMAGE_PIXELS))


def wait_for_picture(page: Any, already: Sequence[str], timeout_seconds: float, sent: Sequence[str] = ()) -> str:
    """Waits for a picture Meta has not shown before, by source: it keeps one, so counting proves nothing."""
    seen = set(already)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        fresh = [src for src in big_images(page) if src not in seen]
        if fresh:
            return settled(page, seen, fresh[-1])
        refuse_if_blocked(page, sent)
        time.sleep(POLL_SECONDS)
    raise ImageError(
        f"Meta AI sent no picture within {timeout_seconds:.0f}s. Its last words were: "
        f"{page.inner_text('body')[-LAST_CHARACTERS:].strip()}"
    )


def settled(page: Any, seen: set[str], src: str) -> str:
    """Meta swaps a preview for the finished picture, so ask again after a pause and take the newest."""
    time.sleep(SETTLE_SECONDS)
    fresh = [found for found in big_images(page) if found not in seen]
    return fresh[-1] if fresh else src


def download(page: Any, src: str) -> bytes:
    """Fetched inside the page, so the picture comes down the same logged-in session that drew it."""
    return base64.b64decode(page.evaluate(FETCH_AS_BASE64, src))


def open_profile(playwright: Any, profile_dir: Path) -> tuple[Any, Any]:
    """Headed on purpose: this is the creator watching their own session, not a hidden one."""
    context = playwright.chromium.launch_persistent_context(str(profile_dir), headless=False)
    return context, (context.pages[0] if context.pages else context.new_page())


class PlaywrightMetaChat:
    """A real browser on the creator's own profile. It never sees a password: they signed in by hand."""

    def __init__(self, profile_dir: Path, timeout_seconds: float) -> None:
        self.profile_dir = profile_dir
        self.timeout_seconds = timeout_seconds
        self._playwright: Any = None
        self._context: Any = None
        self._page: Any = None
        self._asked = False

    def request_image(self, prompt: str) -> bytes:
        page = self._opened()
        if self._asked:  # the launch already landed on a clean thread
            start_thread(page)
        self._asked = True
        return ask_for_image(page, prompt, self.timeout_seconds)

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._playwright, self._context, self._page = None, None, None

    def _opened(self) -> Any:
        """The profile directory is the whole credential store, and the creator filled it by hand."""
        if self._page is None:
            if not self.profile_dir.is_dir():
                raise ImageError(LOGIN_HELP)
            self._page = self._launch()
        return self._page

    def _launch(self) -> Any:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._context, page = open_profile(self._playwright, self.profile_dir)
        page.set_default_timeout(self.timeout_seconds * 1000)
        page.goto(HOME_URL)
        refuse_if_blocked(page)
        return page
