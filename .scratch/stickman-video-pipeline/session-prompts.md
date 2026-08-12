# Session Prompts — Stickman Video Pipeline

One prompt per ticket, each self-contained for a fresh Claude Code session. Copy the whole block including the shared rules (fresh sessions have no memory of this one).

Usage notes:

- Run them in order: 01 → 02 → 03 → 04 → 05 → 06. Tickets 02 and 03 only depend on 01, but both modify the server module — run them in parallel only if you use separate git worktrees; sequential is simpler.
- Each session ends by ticking the acceptance boxes it verified and setting `Status: ready-for-human`. The remaining human checks (listen to a clip, watch the video) are yours — tick those boxes yourself after checking, then start the next session.
- First runs are slow: ticket 01 downloads ~2.5 GB of CUDA torch wheels, 02 ~330 MB Kokoro weights, 03 ~7 GB SDXL weights.

---

## Ticket 01 — Walking skeleton

```
Implement ticket 01 of the stickman video pipeline.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — architecture, tool contracts, and testing decisions; follow them exactly
2. .scratch/stickman-video-pipeline/issues/01-run-lifecycle-walking-skeleton.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md and docs/adr/ — use this vocabulary in code and docs; ADR-0001 and ADR-0002 are binding

Scope: only ticket 01 (package + config + Script/Scene models + Run store + the three lifecycle tools + project-scoped MCP registration). Do not start later tickets or add TTS/image/render code.

Rules:
- TDD. The default test suite must stay offline and GPU-free; anything needing model weights or CUDA is opt-in behind a pytest marker excluded by default.
- Environment: Windows 11, uv with Python 3.11.9, RTX 3060 12GB (CUDA driver 13.3 — cu124 torch wheels work), ffmpeg 8.1 already on PATH. The repo path contains spaces — always quote paths in commands.
- Server name stickman_mcp; every tool name prefixed stickman_; tool failures return actionable "Error: ..." strings naming the fixing tool.
- Commit after each green test cycle with a clear message; never push.

When done: verify every acceptance criterion against real command output, tick the verified checkboxes in the ticket file, append an evidence summary under a "## Comments" heading, set Status: ready-for-human, and list anything left for me to check by hand.
```

---

## Ticket 02 — Narration slice (Kokoro)

```
Implement ticket 02 of the stickman video pipeline.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — architecture and testing decisions; follow them exactly
2. .scratch/stickman-video-pipeline/issues/02-narration-slice.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md and docs/adr/ — ADR-0001 is central here: Narration Clip length IS Scene duration; no transcription anywhere

Blocker check: open issues/01-run-lifecycle-walking-skeleton.md and confirm its criteria are ticked. If not, stop and tell me.

Scope: only ticket 02 — the stickman_synthesize_narration tool, Kokoro behind the TTSEngine protocol, skip-existing resume behavior, espeak-ng installation, and the README notes on raising the MCP tool timeout. No image or render work.

Rules:
- TDD at the tool seam with a fake TTS engine (writes silent WAVs of known duration; keeps a call log). Real Kokoro lives only in a marker-excluded smoke test.
- espeak-ng is NOT installed on this machine — install it (winget has eSpeak-NG) as part of this ticket; if Kokoro can't find the library, the PHONEMIZER_ESPEAK_LIBRARY environment variable is the fallback.
- Environment: Windows 11, uv, RTX 3060; the repo path contains spaces — quote paths.
- Commit after each green test cycle; never push.

When done: run the real smoke test once, verify every criterion, tick the verified checkboxes in the ticket file, append evidence under "## Comments", set Status: ready-for-human, and tell me which clips to listen to.
```

---

## Ticket 03 — Image slice (SDXL background job)

```
Implement ticket 03 of the stickman video pipeline.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — architecture and testing decisions; follow them exactly
2. .scratch/stickman-video-pipeline/issues/03-image-slice.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md and docs/adr/ — Style Prefix and Visual Bible are defined there

Blocker check: open issues/01-run-lifecycle-walking-skeleton.md and confirm its criteria are ticked. If not, stop and tell me.

Scope: only ticket 03 — the file-backed background job manager, stickman_generate_images + stickman_job_status + stickman_regenerate_image, and SDXL-Lightning behind the ImageBackend protocol. No render work.

Key contracts from the spec:
- Style Prefix + negative prompt are applied server-side to every prompt; the Script's Image Prompts stay content-only.
- Batch seeds are deterministic (base seed + scene id); regenerate without an explicit seed must reroll randomly; a replacement image_prompt updates the saved Script BEFORE generating (Script is the single source of truth).

Rules:
- TDD at the tool seam with a fake image backend (writes tiny PNGs; keeps a call log proving prompts/seeds). Real SDXL lives only in a marker-excluded smoke test (~7 GB one-time download on first run).
- Job-start tool calls must return immediately; polling reads job state from the job file.
- Environment: Windows 11, uv, RTX 3060 12GB fp16 CUDA; the repo path contains spaces — quote paths.
- Commit after each green test cycle; never push.

When done: run the real smoke test once, verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and tell me which images to eyeball.
```

---

## Ticket 04 — Render slice (Video Package)

```
Implement ticket 04 of the stickman video pipeline.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — architecture and testing decisions; follow them exactly
2. .scratch/stickman-video-pipeline/issues/04-render-slice.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md and docs/adr/ — the Video Package and the ADR-0001 timing rule live there

Blocker check: open issues/02-narration-slice.md AND issues/03-image-slice.md and confirm their criteria are ticked. If not, stop and tell me.

Scope: only ticket 04 — the SRT builder, the ffmpeg assembly (narration track with inter-Scene gaps, still-image concat with per-Scene durations, optional looped/trimmed music bed at the configured dB), stickman_render_video as a background job, stickman_list_music, and stickman_save_metadata.

Key contracts from the spec:
- Image k holds the screen for exactly its clip duration plus the configured gap; hard cuts only; total duration = sum of clip durations + one gap per Scene.
- Output: 1920x1080, 30 fps, H.264 yuv420p, AAC, faststart. Non-16:9 images are padded, never stretched.
- SRT cues mirror the Scenes exactly; timing derives from clip lengths only (never transcription).

Rules:
- TDD at the tool seam. ffmpeg runs for REAL in the default suite on tiny generated fixtures (solid-color PNGs, sub-second tones); assert output duration with ffprobe within 0.35 s; assert SRT as exact text. Engines stay fake — no GPU, no downloads.
- Include one end-to-end default-suite test: create -> script -> narrate -> images -> render, all with fakes plus real ffmpeg.
- Environment: Windows 11, uv, ffmpeg 8.1 and ffprobe on PATH; the repo path contains spaces — quote paths.
- Commit after each green test cycle; never push.

When done: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and tell me which rendered video to watch and what to listen for in the music mix.
```

---

## Ticket 05 — /produce-video skill + first real run

```
Implement ticket 05 of the stickman video pipeline. I will stay in this session for the real smoke runs — plan on my participation.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — the workflow, Checkpoints, Yolo Mode, and metadata rules are specified there
2. .scratch/stickman-video-pipeline/issues/05-produce-video-skill.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md and docs/adr/ — the skill must speak this vocabulary (Run, Scene, Checkpoint, Yolo Mode, Video Package)

Blocker check: open issues/04-render-slice.md and confirm its criteria are ticked. If not, stop and tell me.

Scope: only ticket 05 — the produce-video skill file under .claude/skills/, the README (one-time setup incl. the MCP tool timeout raise, usage, tuning pointer), then the two live verifications with me:
1. Yolo smoke: I'll say "produce a video about <topic>, 4 scenes only, yolo, no music" — it must run to a playable MP4 + SRT + metadata with zero input from me in between.
2. Checkpoint run: same but default mode — it must pause at Script Approval and Image Review and act on my feedback, including regenerating one image I pick.

Skill content rules (from the spec): hook-first scripts of 30-45 Scenes (2-4 sentences each), Illustrative Format image prompts with NO style words, Visual Bible for recurring elements, duration warning outside 4.5-10.5 minutes, metadata with AI-generation disclosure and a max-60-char title, reminder about YouTube's synthetic-content declaration.

Rules:
- Environment: Windows 11, uv; the repo path contains spaces — quote paths.
- Commit the skill and README when done (not the generated video Run folders); never push.

When done: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and hand me the video path for the final human check.
```

---

## Ticket 06 — Channel tuning (style + voice lock)

```
Implement ticket 06 of the stickman video pipeline. I will stay in this session — the whole point is that I pick the channel's style and voice.

Read first, in order:
1. .scratch/stickman-video-pipeline/spec.md — the tuning session is described under Implementation Decisions and Further Notes
2. .scratch/stickman-video-pipeline/issues/06-channel-tuning.md — your ticket; the acceptance checkboxes are the definition of done
3. CONTEXT.md — Style Prefix is a locked, channel-wide concept

Blocker check: open issues/02-narration-slice.md AND issues/03-image-slice.md and confirm their criteria are ticked. If not, stop and tell me.

Scope: only ticket 06 —
1. A style-grid script: at least 4 candidate Style Prefixes x 2 sample scene prompts, rendered through the real image backend, filenames identifying each style; outputs to a gitignored tuning folder.
2. A voice-audition script: one sample narration line synthesized in at least 5 Kokoro voices, filenames identifying each voice; same tuning folder.
3. Run both, then STOP and walk me through the outputs so I pick a style and a voice.
4. Write my picks into the channel config, prove the lock took effect per the ticket's criteria, and mark the tuning session done in the README.

Rules:
- Environment: Windows 11, uv, RTX 3060 (real engines run here — expect model load time); the repo path contains spaces — quote paths.
- Commit the scripts and the updated config; never commit the tuning outputs; never push.

When done: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and confirm which style and voice are now locked.
```
