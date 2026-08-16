# Spec: Stickman Video Pipeline

Status: ready-for-agent

## Problem Statement

The creator wants to run a monetized YouTube channel of 5-10 minute stickman explainer videos as a side income. Producing one such video by hand — writing a retention-oriented script, recording narration, illustrating 30-45 scenes in a consistent style, and assembling everything into a timed video — takes hours per video. AI video SaaS tools cost money per video, and LLM API keys add per-call costs. The creator already pays for a Claude subscription and owns capable hardware (RTX 3060), and wants video production to cost nothing beyond those.

## Solution

A pair of deliverables used from Claude Code under the existing subscription:

1. An MCP server (`stickman_mcp`) exposing dumb, mechanical tools: batch text-to-speech, background-job image generation, and video assembly.
2. A `/produce-video` skill encoding the workflow and quality bar.

The creator gives a Topic in conversation. Claude authors the Script scene-first (per ADR-0001) and does all creative work itself (per ADR-0002); the tools synthesize a Narration Clip per Scene (Kokoro, locally), generate one still image per Scene (SDXL-Lightning, locally, in the channel's locked Style Prefix), and assemble the Video Package: a 1080p MP4 with hard cuts and optional background music, an SRT subtitle file, and upload metadata. Two Checkpoints (Script Approval, Image Review) keep the human in control; Yolo Mode skips them. Every Run is a self-contained folder whose state is derived from files on disk, so any stage resumes after interruption.

## User Stories

1. As a creator, I want to give a one-line Topic and receive a finished Video Package, so that producing a video takes minutes of my attention instead of hours.
2. As a creator, I want the Script authored as ordered Scenes with narration and an Image Prompt each, so that narration, images, subtitles, and timing can never drift apart.
3. As a creator, I want a Script Approval Checkpoint before any synthesis, so that I never waste GPU time on a script I don't like.
4. As a creator, I want to request script edits at the Checkpoint and have them re-saved and re-validated, so that iteration is cheap.
5. As a creator, I want to see the narrated total duration after synthesis, so that I know the video will land in the 5-10 minute range before rendering.
6. As a creator, I want to be warned when the narration falls outside the target range, so that I can lengthen or shorten the Script early.
7. As a creator, I want an Image Review Checkpoint with the images available to eyeball, so that no bad frame ships in the final video.
8. As a creator, I want to regenerate a single Scene's image and get a different result, so that one bad image never forces a batch re-run.
9. As a creator, I want to replace a Scene's Image Prompt and regenerate, so that I can fix content (not just luck) per scene.
10. As a creator, I want Yolo Mode, so that once I trust the pipeline a single message produces a video unattended.
11. As a creator, I want any interrupted Run to resume from what already exists on disk, so that a crash or timeout never restarts finished work.
12. As a creator, I want to query a Run's status at any time, so that I always know which stage it is at and what remains.
13. As a creator, I want long stages to run as background jobs I can poll, so that no single tool call risks a client timeout.
14. As a creator, I want an optional background music bed chosen from my own curated folder, so that music never triggers a Content ID claim on a monetized video.
15. As a creator, I want the music mixed quietly under the narration at a configured level, so that speech always stays intelligible.
16. As a creator, I want an SRT subtitle file whose cues match the spoken Scenes exactly, so that uploads get accurate captions for free.
17. As a creator, I want upload metadata (title, description, tags) saved with the video, including an AI-generation disclosure line, so that uploading is copy-paste and policy-compliant.
18. As a creator, I want every video drawn in one locked channel Style Prefix, so that my channel has a recognizable visual identity.
19. As a creator, I want one locked narration voice, so that my channel has a recognizable audio identity.
20. As a creator, I want a one-off style tuning session with a grid of candidate styles, so that I choose the channel look once from real outputs, not descriptions.
21. As a creator, I want a one-off voice audition across available voices, so that I choose the channel voice by listening.
22. As a creator, I want recurring characters or settings described once in a Visual Bible and repeated verbatim in prompts, so that recurring elements stay consistent across Scenes.
23. As a creator, I want each Scene shown as a single static image with hard cuts and no panning, so that the format stays simple and fast to render.
24. As a creator, I want the image generator and TTS engine to be swappable behind stable interfaces, so that I can replace Stable Diffusion or Kokoro later without touching the pipeline.
25. As a creator, I want everything to run locally under my subscription with no API keys, so that marginal cost per video is zero.
26. As a creator, I want validation errors (bad scene ids, missing files, unknown run) to name the problem and the fixing tool, so that recovery never requires reading server code.

## Implementation Decisions

- Two deliverables: the `stickman_mcp` FastMCP server (Python, managed with uv) and the `/produce-video` skill. The skill owns workflow and quality; the server owns mechanics.
- ADR-0002 governs: no LLM calls inside the server. Claude (the host) writes the Script, Image Prompts, and metadata in-conversation.
- ADR-0001 governs: the Script is authored as Scenes; each Scene's duration is the length of its Narration Clip. No speech-to-text or forced alignment anywhere.
- Server modules, one responsibility each: channel config loading; Script/Scene domain models with validation; Run folder store with disk-derived status; a file-backed background job manager; TTS behind a `TTSEngine` protocol; image generation behind an `ImageBackend` protocol; SRT building; ffmpeg assembly; a thin tool layer wiring them.
- Tool surface (all results JSON; failures are actionable `Error:` strings):
  - `stickman_create_run(topic, slug?)` — new Run folder, returns run id.
  - `stickman_save_script(run_id, script)` — validates and persists the Script; warns when existing derived assets become stale.
  - `stickman_get_run(run_id)` — status derived from disk plus current job.
  - `stickman_synthesize_narration(run_id)` — synchronous batch TTS; skips Scenes that already have clips; returns per-Scene durations.
  - `stickman_generate_images(run_id, only_missing?)` — starts a background job; one image per Scene.
  - `stickman_job_status(run_id)` — poll the Run's current/last job.
  - `stickman_regenerate_image(run_id, scene_id, image_prompt?, seed?)` — synchronous single-Scene regeneration; a new prompt updates the saved Script first (single source of truth); no seed means a random reroll.
  - `stickman_list_music()` — tracks in the curated music folder.
  - `stickman_render_video(run_id, music_track?)` — background job: writes subtitles then assembles the video.
  - `stickman_save_metadata(run_id, title, description, tags)` — persists upload metadata.
- Script contract: topic, title, optional visual_bible (name → canonical description), and scenes, each `{id, narration, image_prompt}` with ids sequential from 1. Narration is ~2-4 sentences (8-15 seconds spoken); a 5-10 minute video is roughly 30-45 Scenes.
- Run contract: one folder per Run named `<date>-<slug>` inside the projects directory (gitignored); Scene assets numbered by zero-padded Scene id; pipeline status is always derived from which files exist, never cached — this is what makes every stage resumable.
- Batch + job pattern (settled in design): TTS is one synchronous batch call; image generation and rendering are background jobs polled via job status, because MCP clients default to a 30-second tool timeout and multi-minute synchronous calls are unreliable. The client-side timeout raise is documented for the one long synchronous call.
- Style enforcement is mechanical, therefore server-side: the tool layer prepends the channel Style Prefix (and applies the negative prompt) to every Image Prompt. Claude's prompts describe scene content only.
- Image seeds are deterministic per Scene (base seed + scene id) for reproducibility; regeneration without an explicit seed rerolls randomly so "try again" always changes the image.
- Engines: Kokoro-82M (Apache-2.0, local, 24 kHz mono, default voice af_heart) behind `TTSEngine`; SDXL base + SDXL-Lightning 4-step LoRA, fp16 on CUDA, generating near-16:9 frames upscaled and padded to the output resolution, behind `ImageBackend`. Both lazy-load on first use.
- Assembly: ffmpeg concatenates the still images with per-Scene display time equal to clip duration plus the configured inter-Scene gap (default 0.4 s), hard cuts only; narration clips are joined with the same gaps into one track; optional music is looped/trimmed under it at a configured negative dB level; output is 1080p30 H.264 (yuv420p) with AAC audio, faststart.
- One channel config file holds the locked Style Prefix, negative prompt, voice, gap, music level, resolutions, sampler settings, and base seed. Tuning it is a one-off setup activity, not a per-video decision.
- Environment: Windows 11, RTX 3060 12GB (CUDA driver 13.3), Python 3.11, uv, ffmpeg already on PATH; espeak-ng must be installed for Kokoro. First real use downloads model weights (~7 GB SDXL + ~330 MB Kokoro).
- The server registers with Claude Code via project-scoped MCP configuration so opening the repo is enough.

## Testing Decisions

- A good test observes external behavior only: call a tool, assert on the JSON response and the files that appear in the Run folder. Tests never reach into module internals.
- Primary seam: the MCP tool surface, exercised as plain functions with test doubles injected for the two engines.
- Secondary seam: the `TTSEngine` / `ImageBackend` protocols — fakes in the default suite (a fake that writes silent WAVs of known duration; a fake that writes tiny PNGs); the same seam is the production swappability point.
- Real engines (Kokoro, SDXL) are covered by opt-in smoke tests behind a marker, excluded from the default run so the suite is fast, offline, and GPU-free.
- ffmpeg is exercised for real in the default suite on tiny generated fixtures (solid-color images, sub-second tones); output duration is asserted with ffprobe within a small tolerance.
- Subtitle timing is asserted against exact expected SRT text, including the gap arithmetic and hour rollover.
- The full pipeline (create → script → narrate → images → render) runs end-to-end in the default suite with fake engines and real ffmpeg.
- Prior art: none — greenfield repo; pytest is the framework.

## Out of Scope

- ~~Meta AI / Playwright browser automation as an image backend.~~ **Brought into scope 2026-08-14** as ticket 07, after local SDXL output was rejected on style. It is an addition behind the `ImageBackend` protocol, not a replacement: local generation stays the default until the creator switches it. See that ticket for the credential, anti-detection, account-risk, and commercial-rights constraints.
- Intro/outro end-cards, thumbnails, panning/zoom/motion effects, transitions other than hard cuts.
- Languages other than English; multiple simultaneous Runs; per-video style or voice choices.
- YouTube upload automation and analytics.
- Headless scheduled production (works via Claude Code headless mode by construction, but is not tested by this effort).

## Further Notes

- Monetization compliance: metadata always includes an AI-generation disclosure line, and the workflow reminds the creator to tick YouTube's altered/synthetic content declaration on upload.
- Music licensing stays the creator's responsibility by design — the pipeline only uses tracks they placed in the curated folder (YouTube Audio Library is the recommended source).
- The channel-branding tuning session (style grid + voice audition) gates the first production video; until then defaults are placeholders.
- Design history: the ubiquitous language lives in CONTEXT.md; the two architectural commitments are docs/adr/0001 (scene-first, no timestamper) and docs/adr/0002 (creative work in the host).
