# 03 — Image slice: Scenes get pictures (SDXL background job)

**What to build:** `stickman_generate_images` starts a background job that produces one still image per Scene with SDXL-Lightning locally, returning immediately; the creator (via Claude) polls `stickman_job_status` for progress and gets a folder of images to review at the Image Review Checkpoint. `stickman_regenerate_image` fixes individual Scenes: no arguments beyond the scene id means "reroll" (new random seed, different image); a replacement Image Prompt updates the saved Script first — the Script stays the single source of truth. The channel Style Prefix and negative prompt are applied server-side to every prompt; batch seeds are deterministic (base + scene id). SDXL hides behind the `ImageBackend` protocol — the swap point promised in design ("if I'm not satisfied with SD, we change it"). Includes the file-backed job manager this and ticket 04 share.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 01 — Walking skeleton: Run lifecycle over MCP.

**Status:** ready-for-human

- [x] `uv run pytest` (default suite) passes using a fake backend — no model download, no GPU.
- [x] Starting the job returns immediately (well under the 30 s default tool timeout) with the total Scene count; `stickman_job_status` then shows running with a rising done-count, and finally state done with done == total.
- [x] With the fake backend, the job produces one image per Scene at the documented naming convention; `stickman_get_run` shows the images completion count equal to the scene count.
- [x] Starting a second job while one runs returns an `Error:` string telling the caller to poll the current job.
- [x] A job whose backend throws ends in state error with the exception message readable via `stickman_job_status`, and re-running with only_missing set completes just the unfinished Scenes.
- [x] Fake-backend call log proves every prompt was prefixed with the configured Style Prefix and carried the configured negative prompt, and batch seeds equal base seed + scene id.
- [x] `stickman_regenerate_image` with only a scene id produces a byte-different image than the batch one (random reroll); with an explicit seed equal to the batch rule it reproduces the batch image byte-identically (determinism).
- [x] `stickman_regenerate_image` with a new Image Prompt persists that prompt into the saved Script (visible on re-read) before generating.
- [x] `stickman_regenerate_image` for a scene id not in the Script returns an `Error:` string naming the valid id range.
- [x] Opt-in smoke test (marked, excluded by default): real SDXL-Lightning generates an image at the configured resolution from a stickman prompt.
- [ ] Human check on the real smoke output: the image reads as a stickman line drawing consistent with the Style Prefix.

## Comments

### Evidence (2026-08-13)

Built test-first at the pre-agreed seam: the tool functions called directly with a fake `ImageBackend` that writes real 1x1 PNGs coloured by seed and logs every prompt and seed. Final state — `uv run pytest`: **43 passed, 2 deselected in 0.98s**; `uv run mypy`: **Success: no issues found in 18 source files**.

**Offline suite (criterion 1).** `torch` and `diffusers` are imported inside `SDXLLightningBackend`'s methods, never at module scope, so the default run touches no GPU and downloads nothing. The two smoke tests are excluded by the existing `-m 'not smoke'` default.

**Fake-backend criteria (2-9).** One test per criterion in `tests/test_images.py`, each asserting on tool JSON and files in the Run folder:

```
job start                -> elapsed < 1.0s, {"job": "images", "state": "running", "done": 0, "total": 3}
paced backend            -> done 1 while running, then state done with done == total == 3
images/                  -> 001.png, 002.png, 003.png; stickman_get_run images == 3
second job               -> Error: a images job is already running ... Call stickman_job_status to follow it.
backend throws on #2     -> state error, "the image backend failed on 002.png: CUDA out of memory",
                            resume names only_missing; images == 1
only_missing re-run      -> seeds [4244, 4245] only, then images == 3
call log                 -> every prompt starts with the configured Style Prefix, carries the
                            configured negative prompt; seeds [4243, 4244, 4245] from base_seed 4242
reroll                   -> seed != 4244 and the file's bytes change
seed=4244                -> bytes identical to the batch image
new image_prompt         -> script.json already held the new prompt when the backend was called
scene 7 of 3             -> Error: ... its Script has Scenes 1 to 3 ...
```

Each test was confirmed to bite: the immediate-return assertion fails if `Job.start` joins the worker (10.0s vs 1.0s), the concurrency guard test fails with the guard disabled, the prompt/seed assertions fail if the prefix or `+ scene_id` is dropped, and the ordering assertion fails if the Script is saved after drawing rather than before.

**Real SDXL (criterion 10).** `uv run pytest -m smoke -k sdxl` -> **1 passed in 926s**, almost all of it the one-time 6.6 GB download. The test asserts the PNG's IHDR header is exactly the configured 1344x768.

**Real end-to-end run (beyond the criteria).** The whole slice was then driven through the tool surface against the real backend, not just the protocol:

```
generate_images returned in 0.000s     (with SDXL on the other side)
job finished in 46.1s                  3 Scenes, including a ~40s model load -> about 2s per image
get_run  -> {"images": 3, "job": {"state": "done", "done": 3, "total": 3}}
regenerate scene 2 -> seed 466763513 (random reroll), 6.9s with the model already loaded
```

### Left for you to check by hand

1. **Eyeball these, and expect to be unimpressed by the style, not the plumbing:**
   - `projects/smoke/sdxl-lightning.png` — the smoke output.
   - `projects/2026-08-13-real-backend-check/images/001.png` .. `003.png` — a real batch.
   - `projects/smoke/guidance-1.0.png` vs `guidance-2.5.png` — same prompt and seed, guidance changed.

   **Criterion 11 is deliberately left unticked.** The images come out as monochrome minimalist illustrations — filled silhouettes with scenery and gradients — not stickman line drawings on plain white. The mechanism is right (the Style Prefix reaches the model, the resolution is exact, seeds reproduce), but the placeholder prefix does not buy the channel look. That is exactly what ticket 06 exists to fix from real output, and ticket 01's evidence says not to hand-tune it before then.

2. **Restart the MCP server.** `uv sync` could not replace `stickman-mcp.exe` while the registered server held it open, so both server processes were stopped mid-session. Claude Code relaunches it on restart (or `/mcp`); the three new tools appear then.

### Decisions worth knowing

- **The negative prompt cannot bite at `guidance_scale = 1.0`.** diffusers only runs classifier-free guidance above 1.0, and SDXL-Lightning is distilled to be used without it. It is passed to the backend regardless (the criterion 6 test proves that), and `guidance-2.5.png` shows what raising it buys: a cleaner background, but colour still leaks in and each image costs roughly twice the time. A tuning knob for ticket 06, not a default to change now.
- **The Visual Bible is deliberately not expanded server-side.** The spec puts only style enforcement in the tool layer ("the tool layer prepends the channel Style Prefix (and applies the negative prompt)"), so repeating a Bible entry verbatim stays the `/produce-video` skill's job in ticket 05.
- **`only_missing` defaults to false.** Criterion 5 reads "re-running with only_missing set", so a plain call redraws the batch; the deterministic seeds make that visually a no-op.
- **A job file left saying `running` with no live worker is reported as an error** (with the resume instruction the starting tool supplied), because a stale file would otherwise block that Run's jobs forever. It is derived at read time, never written back, so `stickman_job_status` stays genuinely read-only.
- **The job file is not published by rename.** On Windows `os.replace` raises `PermissionError` (WinError 5) when a poller has the file open — this actually failed the first test run. A module-level re-entrant lock guards reads, writes, and worker registration instead; PNG and WAV writes keep the rename idiom because nothing reads them mid-write.
- Code review (standards + spec axes) caught two real defects, both fixed: `jobs.py` carried an images-specific resume message that ticket 04's render job would have inherited falsely, and a poll landing between "write running" and "thread started" could have declared a healthy job dead — which would then have let a second job through the guard.
- `stickman_get_run` now carries the job block, per the spec's "status derived from disk plus current job".
