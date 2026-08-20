"""One-off: open the browser profile the Meta AI backend uses, so you can sign in by hand.

Nothing here reads, types or stores a password: you type it into Meta's own page, and Meta
leaves its session in the profile folder. Delete that folder to sign out.

Run with: uv run python scripts/meta_login.py
"""

from __future__ import annotations

from stickman_mcp.config import load_channel_config
from stickman_mcp.meta_ai import HOME_URL, open_profile


def main() -> None:
    from playwright.sync_api import sync_playwright

    config = load_channel_config()
    config.meta_profile_dir.mkdir(parents=True, exist_ok=True)
    print(f"Profile folder: {config.meta_profile_dir}")
    print("Sign in to Meta AI in the window that opens, then close the window to finish.")

    with sync_playwright() as playwright:
        _, page = open_profile(playwright, config.meta_profile_dir)
        page.goto(HOME_URL)
        page.wait_for_event("close", timeout=0)

    print("Saved. Set image.backend to 'meta-ai' in channel.toml and restart the server.")


if __name__ == "__main__":
    main()
