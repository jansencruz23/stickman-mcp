# 01 — Walking skeleton: Run lifecycle over MCP

**What to build:** From a Claude Code conversation in this repo, the creator can create a Run for a Topic, save a Script (ordered Scenes with narration and Image Prompts), and ask for the Run's status at any time. The `stickman_mcp` server is registered project-scoped, so opening the repo is enough — no manual server start. This slice establishes the package (Python + uv, CUDA-capable torch), the channel config file, the Script/Scene validation rules, the Run folder convention with disk-derived status, and the tool layer with its error convention (`Error:` strings that name the problem and the fixing tool).

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-human

- [x] `uv sync` completes, and `uv run python -c "import torch; print(torch.cuda.is_available())"` prints `True` on this machine (RTX 3060).
- [x] `uv run pytest` passes with zero failures and zero GPU/model downloads (default suite is offline).
- [x] The MCP Inspector (or Claude Code `/mcp`) connects to the registered server and lists `stickman_create_run`, `stickman_save_script`, and `stickman_get_run` with descriptions.
- [x] Calling `stickman_create_run` with a topic returns a run id matching the `<date>-<slug>` convention, and the Run folder with its audio and images subfolders exists on disk.
- [x] Creating two Runs for the same topic on the same day yields two distinct run ids (collision suffix).
- [x] Saving a valid Script returns the scene count; the saved file round-trips (reading the Run back shows the same scenes).
- [x] Saving a Script with non-sequential scene ids (e.g. 1, 3) returns an `Error:` string that names the offending ids — nothing is written.
- [x] Saving a Script over one that already has derived assets returns a staleness warning naming the remedy tools.
- [x] `stickman_get_run` reports has_script, scene_count, per-stage completion counts, and video_rendered, and the counts visibly change when files are added to or removed from the Run folder.
- [x] `stickman_get_run` for a nonexistent run id returns an `Error:` string naming `stickman_create_run` as the fix.
- [x] The channel config file loads with documented defaults (voice, 0.4 s gap, 1080p30 output, style prefix present), and a malformed config fails with a clear message at server start, not mid-pipeline.

## Comments

### Evidence (2026-08-13)

Built test-first at the pre-agreed seam: the tool functions called directly, asserting on JSON responses and files in the Run folder. Final state — `uv run pytest`: **19 passed in 0.20s**; `uv run mypy`: **Success: no issues found in 10 source files**.

**Environment (criterion 1).** `uv sync` exit 0, resolving 65 packages. `uv run python -c "import torch; ..."` printed:

```
2.6.0+cu124
True
NVIDIA GeForce RTX 3060
```

**Offline suite (criterion 2).** No `torch`, `cuda`, `diffusers` or `kokoro` import exists anywhere in `src/` (grep clean), so the default suite touches no GPU and downloads nothing. A `smoke` marker is registered and excluded by default in `pyproject.toml` for the later real-engine tickets.

**Registration (criterion 3).** Verified by launching the server over stdio with the `command`/`args` read verbatim out of `.mcp.json`, using the official MCP Python client — the same handshake the Inspector performs:

```
connected: stickman_mcp v0.1.0
- stickman_create_run: Start a new Run for a Topic and prepare its folder on disk.
- stickman_save_script: Validate and persist a Run's Script: the ordered Scenes narration and images derive from.
- stickman_get_run: Report a Run's progress, derived from the files currently in its folder.
```

**Lifecycle (criteria 4-10).** Driven through that same live stdio session, not just in-process:

```
create_run       -> 2026-08-13-how-compound-interest-works
create_run again -> 2026-08-13-how-compound-interest-works-2 (collision suffix)
folders          -> ['audio', 'images']
save_script      -> {"run_id": "...", "scene_count": 2}
bad ids          -> Error: scene ids must run sequentially from 1 with no gaps or reordering;
                    got 1, 3 but expected 1, 2. Nothing was written; fix the script and call
                    stickman_save_script again.
script.json kept -> True          (the rejected save wrote nothing)
stale re-save    -> {"scene_count": 2, "warning": "Assets generated from the previous Script are
                    now stale: 1 narration clip(s) in audio/ (stickman_synthesize_narration).
                    Delete the affected files, then re-run the tool named beside each, because
                    those tools skip Scenes that already have assets."}
get_run          -> {"has_script": true, "scene_count": 2, "narration_clips": 1, "images": 1,
                    "video_rendered": false}
after deleting an image -> 0      (counts follow the disk, nothing is cached)
unknown run      -> Error: no Run named '2026-01-01-nope'. Call stickman_create_run to start one.
```

**Config (criterion 11).** `channel.toml` ships the documented defaults and a test asserts them against the real file (voice set, style prefix non-empty, 0.4 s gap, 1920x1080@30). `main()` loads the config eagerly before `server.run()`, so a broken config aborts startup; a test proves it by asserting the server never starts, and the guard was removed once to confirm the test actually fails without it. Unparseable TOML, out-of-range values, missing required keys, and misspelled keys each raise a `ConfigError` naming the file and the setting.

### Decisions worth knowing

- **`MCPServer`, not `FastMCP`.** The current SDK (`mcp` 2.0.0) renamed FastMCP to `MCPServer` and dropped `mcp.server.fastmcp`. Same high-level decorator server the spec intends; the dependency floor is pinned `mcp>=2.0.0` because the import does not exist in 1.x.
- **The staleness warning is gated on the Script actually changing**, and names only the affected stage. Spec wording is "warns when existing derived assets become stale"; warning on every re-save would fight user story 4 ("iteration is cheap") by telling the creator to delete assets that are still good. Re-saving an unchanged Script is silent; editing only narration names only `stickman_synthesize_narration`.
- Scene ids are validated before anything touches disk, so a rejected save leaves the previous `script.json` intact.
- All config keys the spec enumerates (music level, image size, sampler steps, base seed) are loaded now even though this slice has no consumer for them, because the spec specifies one config file holding all of them.

### Left for you to check by hand

1. ~~Restart Claude Code and confirm the server registers.~~ **Confirmed live.** After the restart, Claude Code loaded `.mcp.json`, exposed the three tools as `mcp__stickman_mcp__*`, and a real call through Claude Code's own MCP client returned the expected error convention: `Error: no Run named '2026-01-01-not-a-real-run'. Call stickman_create_run to start one.` Criterion 3 is therefore verified through the Claude Code UI path as well as the direct stdio handshake.
2. **Skim `channel.toml`** and confirm the placeholder Style Prefix and `af_heart` voice are acceptable stand-ins. Do not hand-tune them now — ticket 06 picks both from real generated output, which is the point of that session.
3. `import torch` prints a `Failed to initialize NumPy` UserWarning because numpy is not installed yet. Harmless here (nothing in `src/` imports torch); numpy arrives as a transitive dependency with Kokoro in ticket 02.

### Known prerequisites for the next tickets

- `espeak-ng` is confirmed **not installed** — ticket 02 installs it (winget), expect a UAC prompt.
- Disk: 144 GB free, comfortably above the ~7.3 GB of Kokoro + SDXL weights that tickets 02 and 03 download.
