# 07 — Meta AI image backend via Playwright

**What to build:** A second `ImageBackend` that produces Scene images by driving Meta AI (meta.ai) in a real browser instead of generating locally, selected by a setting in the channel config. The creator logs into Meta once by hand in a persistent browser profile; from then on a Run's images are requested in a single chat thread, one Scene at a time in order, and each returned image is downloaded into the Run folder under the existing naming convention. Every tool in the pipeline (`stickman_generate_images`, `stickman_job_status`, `stickman_regenerate_image`) behaves identically to the local backend — only the source of the pixels changes.

Local SDXL stays in the repo and stays the default until the creator switches it, so this is an addition, not a replacement.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 03 — Image slice (the `ImageBackend` protocol and the job/regenerate tools are the seam this plugs into).

**Status:** ready-for-agent

## Constraints that are not negotiable in implementation

- **No credentials anywhere in code, config, or logs.** Authentication is a persistent Playwright browser profile directory that the creator populates by logging in manually. The repo never reads, stores, or types a Meta password, cookie value, or token. This follows the project's AI restrictions in CLAUDE.md.
- **No anti-detection, fingerprint spoofing, or CAPTCHA solving.** This is plain automation of the creator's own logged-in session. If Meta presents a checkpoint, CAPTCHA, or block, the backend fails loudly with an actionable message and stops — it does not attempt to evade, and it does not silently retry in a loop.
- **Sequential and unhurried.** One request at a time in one thread, with a configurable delay between Scenes. No parallel tabs, no burst requests.
- **Known risks, accepted by the creator and recorded here:** Meta's terms prohibit automated access to their products even while logged in, so the account used may be checkpointed or banned; and Meta publishes no statement on commercial rights to generated output, which is unresolved for a monetized channel. Use a Meta account the creator is willing to lose, not a primary personal account.

## Acceptance criteria

- [ ] `uv run pytest` (default suite) passes with no browser launched and no network access — the backend's page interactions are tested against a local stub page or a mocked Playwright surface, never against meta.ai.
- [ ] The backend satisfies the same `ImageBackend` contract as the local one, proven by running the existing image-slice test suite against it with the browser layer faked (same prompt/seed/destination behaviour, same `ImageError` convention).
- [ ] Selecting the backend is a single channel-config setting; with it unset the pipeline uses local SDXL exactly as today, proven by a test asserting the default selection.
- [ ] Grepping the repo for credential-shaped material (password, cookie, token, session id) returns nothing, and the browser profile directory is gitignored.
- [ ] With no valid session in the profile, the backend fails with an `Error:` string telling the creator to run the documented one-time manual login — it does not hang, does not prompt for a password, and does not retry.
- [ ] A CAPTCHA, checkpoint, or rate-limit page produces a distinct, actionable `Error:` naming what Meta showed, and the job ends in state `error` with that message readable via `stickman_job_status`.
- [ ] Live run, 3-Scene Run: all three images arrive in the Run folder under the existing `NNN.png` convention, in Scene order, from one chat thread.
- [ ] Live run: `stickman_regenerate_image` for one Scene replaces only that Scene's image and leaves the others byte-identical.
- [ ] Live run: an interrupted batch resumes with `only_missing` and requests only the Scenes still lacking images.
- [ ] The configured inter-Scene delay is observed in a live run (measured, not assumed).
- [ ] README documents the one-time manual login, the account-risk and commercial-rights caveats above, and how to switch back to local SDXL.
- [ ] Human check: the returned images match the reference style the creator is aiming for well enough to keep the backend. **If they do not, this ticket's outcome is "tested and rejected" — record that in Comments and keep local SDXL as the default rather than iterating on selector work.**

## Notes for whoever picks this up

- Meta has no public image-generation API; the Meta Model API covers a reasoning model only, and business image access is an ads product. Browser automation is the only route, which is why this ticket exists in this shape.
- Meta AI's current image model is marketed on photorealism and in-image text. There is no evidence either way about its stick-figure quality, which is precisely what the final criterion is there to settle — cheaply, before any selector-hardening effort is spent.
- Expect the page structure to change without notice. Prefer role- and text-based locators over brittle CSS paths, and keep every selector in one clearly marked module so a UI change is a one-file fix.
