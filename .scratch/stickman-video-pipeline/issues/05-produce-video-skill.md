# 05 — /produce-video skill and the first real topic-to-video run

**What to build:** The conversation workflow that makes the tools a product. A `/produce-video` skill instructs Claude to: write a retention-oriented Script (hook first, 30-45 Scenes of 2-4 sentences, Illustrative Format image prompts with no style words, Visual Bible for recurring elements), pause at the Script Approval and Image Review Checkpoints (skipped in Yolo Mode), drive the tool sequence with job polling and duration warnings (offer to lengthen/shorten outside 4.5-10.5 minutes), handle music selection, and finish with metadata that always includes an AI-generation disclosure plus the reminder to tick YouTube's synthetic-content declaration. A README documents one-time setup (uv sync, espeak-ng, timeout raise, model downloads, music folder). Acceptance is a real production smoke run.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 04 — Render slice.

**Status:** ready-for-agent

- [ ] The skill is listed/invocable in a fresh Claude Code session in this repo.
- [ ] Real smoke run, Yolo Mode: a single message ("produce a video about <topic>, 4 scenes only, yolo, no music") yields a Run folder containing a playable MP4, an SRT, and metadata — with no human input between the message and the deliverables.
- [ ] Real run, default mode: the workflow stops and waits at Script Approval (script shown scene-by-scene) and again at Image Review (images folder named, regeneration offered) — verified by observing both pauses in conversation.
- [ ] During Image Review, regenerating one Scene by id visibly replaces that image and no others, and the re-rendered video uses the replacement.
- [ ] The saved metadata contains the AI-generation disclosure line, a title of at most 60 characters, and 10-15 tags.
- [ ] The skill's duration rule fires: a deliberately short test Script triggers the lengthen/shorten offer before rendering.
- [ ] README setup section verified by execution on this machine: following it top-to-bottom on a clean checkout reaches a working `stickman_get_run` call (documented timeout raise included).
- [ ] Human check of the smoke video: narration matches the Script, images match their Scenes' prompts, cuts land at narration boundaries, style is consistent across Scenes.
