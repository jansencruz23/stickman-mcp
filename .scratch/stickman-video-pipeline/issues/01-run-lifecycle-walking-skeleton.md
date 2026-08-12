# 01 — Walking skeleton: Run lifecycle over MCP

**What to build:** From a Claude Code conversation in this repo, the creator can create a Run for a Topic, save a Script (ordered Scenes with narration and Image Prompts), and ask for the Run's status at any time. The `stickman_mcp` server is registered project-scoped, so opening the repo is enough — no manual server start. This slice establishes the package (Python + uv, CUDA-capable torch), the channel config file, the Script/Scene validation rules, the Run folder convention with disk-derived status, and the tool layer with its error convention (`Error:` strings that name the problem and the fixing tool).

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `uv sync` completes, and `uv run python -c "import torch; print(torch.cuda.is_available())"` prints `True` on this machine (RTX 3060).
- [ ] `uv run pytest` passes with zero failures and zero GPU/model downloads (default suite is offline).
- [ ] The MCP Inspector (or Claude Code `/mcp`) connects to the registered server and lists `stickman_create_run`, `stickman_save_script`, and `stickman_get_run` with descriptions.
- [ ] Calling `stickman_create_run` with a topic returns a run id matching the `<date>-<slug>` convention, and the Run folder with its audio and images subfolders exists on disk.
- [ ] Creating two Runs for the same topic on the same day yields two distinct run ids (collision suffix).
- [ ] Saving a valid Script returns the scene count; the saved file round-trips (reading the Run back shows the same scenes).
- [ ] Saving a Script with non-sequential scene ids (e.g. 1, 3) returns an `Error:` string that names the offending ids — nothing is written.
- [ ] Saving a Script over one that already has derived assets returns a staleness warning naming the remedy tools.
- [ ] `stickman_get_run` reports has_script, scene_count, per-stage completion counts, and video_rendered, and the counts visibly change when files are added to or removed from the Run folder.
- [ ] `stickman_get_run` for a nonexistent run id returns an `Error:` string naming `stickman_create_run` as the fix.
- [ ] The channel config file loads with documented defaults (voice, 0.4 s gap, 1080p30 output, style prefix present), and a malformed config fails with a clear message at server start, not mid-pipeline.
