# 07 — Meta AI image backend via Playwright

**What to build:** A second `ImageBackend` that produces Scene images by driving Meta AI (meta.ai) in a real browser instead of generating locally, selected by a setting in the channel config. The creator logs into Meta once by hand in a persistent browser profile; from then on a Run's images are requested in a single chat thread, one Scene at a time in order, and each returned image is downloaded into the Run folder under the existing naming convention. Every tool in the pipeline (`stickman_generate_images`, `stickman_job_status`, `stickman_regenerate_image`) behaves identically to the local backend — only the source of the pixels changes.

Local SDXL stays in the repo and stays the default until the creator switches it, so this is an addition, not a replacement.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 03 — Image slice (the `ImageBackend` protocol and the job/regenerate tools are the seam this plugs into).

**Status:** ready-for-human

## Constraints that are not negotiable in implementation

- **No credentials anywhere in code, config, or logs.** Authentication is a persistent Playwright browser profile directory that the creator populates by logging in manually. The repo never reads, stores, or types a Meta password, cookie value, or token. This follows the project's AI restrictions in CLAUDE.md.
- **No anti-detection, fingerprint spoofing, or CAPTCHA solving.** This is plain automation of the creator's own logged-in session. If Meta presents a checkpoint, CAPTCHA, or block, the backend fails loudly with an actionable message and stops — it does not attempt to evade, and it does not silently retry in a loop.
- **Sequential and unhurried.** One request at a time in one thread, with a configurable delay between Scenes. No parallel tabs, no burst requests.
- **Known risks, accepted by the creator and recorded here:** Meta's terms prohibit automated access to their products even while logged in, so the account used may be checkpointed or banned; and Meta publishes no statement on commercial rights to generated output, which is unresolved for a monetized channel. Use a Meta account the creator is willing to lose, not a primary personal account.

## Acceptance criteria

- [x] `uv run pytest` (default suite) passes with no browser launched and no network access — the backend's page interactions are tested against a local stub page or a mocked Playwright surface, never against meta.ai.
- [x] The backend satisfies the same `ImageBackend` contract as the local one, proven by running the existing image-slice test suite against it with the browser layer faked (same prompt/seed/destination behaviour, same `ImageError` convention).
- [x] Selecting the backend is a single channel-config setting; with it unset the pipeline uses local SDXL exactly as today, proven by a test asserting the default selection.
- [x] Grepping the repo for credential-shaped material (password, cookie, token, session id) returns nothing, and the browser profile directory is gitignored.
- [x] With no valid session in the profile, the backend fails with an `Error:` string telling the creator to run the documented one-time manual login — it does not hang, does not prompt for a password, and does not retry.
- [x] A CAPTCHA, checkpoint, or rate-limit page produces a distinct, actionable `Error:` naming what Meta showed, and the job ends in state `error` with that message readable via `stickman_job_status`.
- [x] Live run, 3-Scene Run: all three images arrive in the Run folder under the existing `NNN.png` convention, in Scene order, from one chat thread.
- [x] Live run: `stickman_regenerate_image` for one Scene replaces only that Scene's image and leaves the others byte-identical.
- [x] Live run: an interrupted batch resumes with `only_missing` and requests only the Scenes still lacking images.
- [x] The configured inter-Scene delay is observed in a live run (measured, not assumed).
- [x] README documents the one-time manual login, the account-risk and commercial-rights caveats above, and how to switch back to local SDXL.
- [x] Human check: the returned images match the reference style the creator is aiming for well enough to keep the backend. **If they do not, this ticket's outcome is "tested and rejected" — record that in Comments and keep local SDXL as the default rather than iterating on selector work.**

## Notes for whoever picks this up

- Meta has no public image-generation API; the Meta Model API covers a reasoning model only, and business image access is an ads product. Browser automation is the only route, which is why this ticket exists in this shape.
- Meta AI's current image model is marketed on photorealism and in-image text. There is no evidence either way about its stick-figure quality, which is precisely what the final criterion is there to settle — cheaply, before any selector-hardening effort is spent.
- Expect the page structure to change without notice. Prefer role- and text-based locators over brittle CSS paths, and keep every selector in one clearly marked module so a UI change is a one-file fix.

## Comments

### Evidence (2026-08-20)

Built test-first at the two pre-agreed seams: the `ImageBackend` contract with the browser layer
faked, and a local stub page (`tests/stubs/`) for the page-interaction logic. Final state —
`uv run pytest`: **104 passed, 1 skipped, 10 deselected in 7.3s**; `uv run pytest -m browser`:
**7 passed**; `uv run mypy`: **Success: no issues found in 30 source files**.

**Offline and browser-free (criterion 1).** Playwright is imported inside the methods that need it,
never at module scope, exactly as the SDXL backend treats torch. A test proves it rather than
asserting it: a subprocess imports `stickman_mcp.server` and reports `'playwright' in sys.modules`
as `False`. Two new markers keep the default run clean — `browser` (a real Chromium against
`file://` stub pages, still offline) and `live` (real meta.ai). `addopts` is now
`-m 'not smoke and not browser and not live'`.

**One contract, two backends (criterion 2).** `tests/test_images.py` shadows the `fake_images`
fixture with a parametrized one, so **every criterion of ticket 03 runs against both backends** —
the local fake, and the real `MetaAIBackend` with a fake chat behind it. 16 tests x 2. Confirmed to
bite: making `MetaAIBackend.generate` skip its write failed 10 `[meta-ai]` tests and no `[local]`
ones.

The one deliberate divergence: **Meta has no seed**, so "regenerating with the batch seed reproduces
the batch image byte-identically" is skipped for it, with the reason in the skip message. The seed
is still accepted and logged through the tool surface unchanged; rerolling works, because Meta draws
afresh every time. Both tool docstrings now say so, since Claude reads those and not the README.

**Failure modes (criteria 5, 6).** `blocking_reason(url, visible_text)` is a pure function over
what the page says, table-driven from `BLOCKERS`. No session gives `LOGIN_HELP` naming
`scripts/meta_login.py`; a security check, checkpoint, restriction and rate limit each give their
own sentence. Proven at the tool surface: the batch ends `state: error` with the text readable via
`stickman_job_status`, and `stickman_regenerate_image` returns it as an `Error:` string.

**Credentials (criterion 4).** Grep over `src/ scripts/ tests/ channel.toml README.md` for
password, passwd, cookie, token, api key, secret, credential and session id returns **eight hits,
all prose saying the server handles none of them** — for example "The server never handles your
password." Authentication is `browser-profile/`, populated by hand via `scripts/meta_login.py`,
gitignored, and covered by a test that reads `.gitignore` and the shipped config together.

### The live run

```
batch, 3 Scenes             done 3/3 in 118.1s; generate_images returned in 0.000s
images/                     001.png, 002.png, 003.png; get_run -> 3 images
chat threads for the batch  1
pauses actually taken       [8.0, 8.0]s against a configured 8.0s
drawn in order              001.png, 002.png, 003.png
regenerate Scene 2          002 REDRAWN, 001 and 003 byte-identical
delete 003, only_missing    003 drawn now, 001 and 002 untouched, job done, 3 images
```

Criterion 10 was measured twice because the first measurement was worthless: timing the gaps
between finished image files gave `[70.7, 27.8]s`, which cannot distinguish a held pause from
Meta being slow. Re-run with a recording `sleep` that really sleeps, the pauses read `[8.0, 8.0]`.

### The style verdict (criterion 12)

**Accepted.** The creator judged `projects/smoke/meta-ai-style-check.png` and the batch, and Meta
matches the locked Style Prefix closely — big round cream circle head, dot eyes and thin eyebrows,
thin black limbs with round joint dots, bold clean outlines, flat muted fills, no gradients. This is
the thing ticket 03 could not get out of SDXL.

**The creator then asked for it as the default**, so `channel.toml` now says
`backend = "meta-ai"`. Two notes on that: the *code* default when the setting is absent is still
`sdxl` (criterion 3's test asserts it), and switching the shipped config makes the accepted
account-ban and commercial-rights risks the normal path rather than an opt-in. Local SDXL is one
line away and needs no login.

### Decisions worth knowing

- **`ImageBackend` gained `close()`, called by `illustration` in a `finally`.** Playwright's sync
  API belongs to the thread that started it, and the image batch runs on a job worker thread while
  a redraw runs on the caller's — so a browser must never outlive the call that opened it. This is
  also what makes a Run exactly one chat thread, without the backend knowing what a Run is. SDXL's
  `close()` is deliberately a no-op: 40 s of weights must outlive a batch.
- **The delay outlives the chat.** Pacing state is not reset by `close()`, so two redraws in a row
  still pause. The spec review caught the opposite behaviour, where every `stickman_regenerate_image`
  fired with no delay at all because the redraw's `close()` cleared the gate.
- **Meta takes a sentence, not a field.** The request is
  `Generate an image: <style prefix> <scene>. Avoid: <negative prompt>.` — the creator chose the
  `Avoid:` clause over dropping the negative prompt. Nothing in the live output suggests Meta drew
  the avoid list as text.
- **`image.width/height/steps/guidance_scale` reach the local backend only.** Meta returns its own
  size (1920x1280 observed) and the render fits and pads it like any other image. Noted in
  `channel.toml` and the README.
- **Whatever Meta answers with is converted to PNG** via Pillow, because `NNN.png` is what the
  render slice promised ffmpeg — Meta serves webp.

### Three real bugs the process caught

1. **The composer selector, caught by the first live run.** `get_by_role("textbox").first` worked
   for Scene 1 and then spent 180 s failing to click for Scene 2: once a thread exists meta.ai adds
   an `<input placeholder="Conversation title">` that sorts first. Rather than guess a fix, the page
   was probed for what it actually offers — the composer is `data-testid="composer-input"` — and the
   locator is now `get_by_role("textbox").and_(get_by_test_id(...))`. The stub page was taught to
   grow the same title box, so the regression is covered offline: the fix was watched failing first.
2. **`click()` before `fill()`, caught by a live run failing then passing.** A later live check timed
   out at 180 s and the retry passed, which is the signature of a flake rather than a break: `click()`
   does a pointer hit test and loses to anything overlapping the composer — the same mechanism as
   bug 1. `fill()` focuses without a hit test, so the click is gone. The live check went from a
   180 s timeout to passing in 21 s.
3. **Block detection read our own prompts, caught by the spec review.** `refuse_if_blocked` matched
   `BLOCKERS` against the whole page body, which includes every message we typed. A Scene whose
   Image Prompt says "a stickman at an airport security check" would have failed itself and every
   later Scene, reporting a Meta security check that never happened. The check now strips what we
   sent before judging. Also watched failing first, and a second test proves the stripping does not
   blind the check to a block that arrives mid-thread.

Standards review also fixed: the module inventory and dependency arrows in `docs/developing.md`,
four duplicated blocker strings, a duplicated browser launch between the backend and the login
script, an unused `url` parameter, and `LAST_WORDS` renamed to `LAST_CHARACTERS` because it slices
characters.

### Left for you

1. **Restart the MCP server.** `uv add` could not replace `stickman-mcp.exe` while the registered
   server held it open, and stopping those processes was blocked, so playwright and pillow were
   installed into the venv directly and `uv.lock` updated. The running server is still on the old
   code. `/mcp` or a restart picks up the Meta backend; a plain `uv sync` will then relink cleanly.
2. **Look at the images** and confirm the style holds across Scenes, not just in one:
   `projects/2026-08-20-meta-live/images/001.png` .. `003.png`, and
   `projects/smoke/meta-ai-style-check.png`. Scene backgrounds vary between Scenes (indoor beige in
   one, outdoor sky and grass in others) — the figures are consistent, the scenery is not, which
   matters for a channel look and is a prompt question rather than a code one.
3. **`playwright install chromium`** is a per-machine step, documented in the README.
