# 03 — Image slice: Scenes get pictures (SDXL background job)

**What to build:** `stickman_generate_images` starts a background job that produces one still image per Scene with SDXL-Lightning locally, returning immediately; the creator (via Claude) polls `stickman_job_status` for progress and gets a folder of images to review at the Image Review Checkpoint. `stickman_regenerate_image` fixes individual Scenes: no arguments beyond the scene id means "reroll" (new random seed, different image); a replacement Image Prompt updates the saved Script first — the Script stays the single source of truth. The channel Style Prefix and negative prompt are applied server-side to every prompt; batch seeds are deterministic (base + scene id). SDXL hides behind the `ImageBackend` protocol — the swap point promised in design ("if I'm not satisfied with SD, we change it"). Includes the file-backed job manager this and ticket 04 share.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 01 — Walking skeleton: Run lifecycle over MCP.

**Status:** ready-for-agent

- [ ] `uv run pytest` (default suite) passes using a fake backend — no model download, no GPU.
- [ ] Starting the job returns immediately (well under the 30 s default tool timeout) with the total Scene count; `stickman_job_status` then shows running with a rising done-count, and finally state done with done == total.
- [ ] With the fake backend, the job produces one image per Scene at the documented naming convention; `stickman_get_run` shows the images completion count equal to the scene count.
- [ ] Starting a second job while one runs returns an `Error:` string telling the caller to poll the current job.
- [ ] A job whose backend throws ends in state error with the exception message readable via `stickman_job_status`, and re-running with only_missing set completes just the unfinished Scenes.
- [ ] Fake-backend call log proves every prompt was prefixed with the configured Style Prefix and carried the configured negative prompt, and batch seeds equal base seed + scene id.
- [ ] `stickman_regenerate_image` with only a scene id produces a byte-different image than the batch one (random reroll); with an explicit seed equal to the batch rule it reproduces the batch image byte-identically (determinism).
- [ ] `stickman_regenerate_image` with a new Image Prompt persists that prompt into the saved Script (visible on re-read) before generating.
- [ ] `stickman_regenerate_image` for a scene id not in the Script returns an `Error:` string naming the valid id range.
- [ ] Opt-in smoke test (marked, excluded by default): real SDXL-Lightning generates an image at the configured resolution from a stickman prompt.
- [ ] Human check on the real smoke output: the image reads as a stickman line drawing consistent with the Style Prefix.
