# Session Prompts — Stickman Video Pipeline

One prompt per ticket, each pasted into a fresh Claude Code session. Every prompt invokes `/implement`, which itself drives `/tdd` at the pre-agreed seams, runs the test suite, finishes with `/code-review`, and commits to the current branch — so the prompts only add what a fresh session can't know: reading order, blockers, seams, environment facts, and the tracker done-protocol.

Usage notes:

- Run in order: 01 → 02 → 03 → 04 → 05 → 06. Tickets 02 and 03 only depend on 01, but both modify the server module — parallelize them only in separate git worktrees; sequential is simpler.
- Each session ends by ticking the acceptance boxes it verified and setting `Status: ready-for-human`. The remaining human checks (listen to clips, watch the video) are yours — tick those boxes yourself after checking, then start the next session.
- First runs are slow: ticket 01 downloads ~2.5 GB of CUDA torch wheels, 02 ~330 MB Kokoro weights, 03 ~7 GB SDXL weights.

---

## Ticket 01 — Walking skeleton

```
/implement .scratch/stickman-video-pipeline/issues/01-run-lifecycle-walking-skeleton.md

Before writing code, read in order: .scratch/stickman-video-pipeline/spec.md (architecture, tool contracts, testing decisions — follow exactly), the ticket above (the acceptance checkboxes are the definition of done), CONTEXT.md and docs/adr/ (vocabulary; ADR-0001 and ADR-0002 are binding).

Pre-agreed seams for /tdd (from the spec's Testing Decisions): primary — the MCP tool surface, called as plain functions, asserting on JSON responses and files in the Run folder; secondary — the TTSEngine/ImageBackend protocols (not needed in this ticket). Default suite stays offline and GPU-free.

Scope: only this ticket — package + config + Script/Scene models + Run store + the three lifecycle tools (stickman_create_run, stickman_save_script, stickman_get_run) + project-scoped MCP registration. No TTS, image, or render code.

Environment: Windows 11; uv with Python 3.11.9; RTX 3060 12GB, CUDA driver 13.3 (cu124 torch wheels work); ffmpeg 8.1 already on PATH; the repo path contains spaces — always quote paths. No typechecker is configured yet — add a fast one if convenient, don't block on it.

Done-protocol beyond /implement: verify every acceptance criterion against real command output, tick the verified checkboxes in the ticket file, append an evidence summary under a "## Comments" heading, set Status: ready-for-human, and list anything left for me to check by hand.
```

---

## Ticket 02 — Narration slice (Kokoro)

```
/implement .scratch/stickman-video-pipeline/issues/02-narration-slice.md

Blocker check first: open .scratch/stickman-video-pipeline/issues/01-run-lifecycle-walking-skeleton.md and confirm its criteria are ticked; stop and tell me if not.

Before writing code, read in order: .scratch/stickman-video-pipeline/spec.md, the ticket above, CONTEXT.md and docs/adr/ (ADR-0001 is central: Narration Clip length IS Scene duration; no transcription anywhere).

Pre-agreed seams for /tdd: the tool surface with a fake TTSEngine (writes silent WAVs of known duration, keeps a call log). Real Kokoro only in a marker-excluded smoke test, run once at the end.

Scope: only this ticket — stickman_synthesize_narration, Kokoro behind TTSEngine, skip-existing resume behavior, espeak-ng installation, README notes on raising the MCP tool timeout.

Environment: Windows 11; uv; the repo path contains spaces — quote paths. espeak-ng is NOT installed — install it (winget has eSpeak-NG) as part of this ticket; if Kokoro can't find the library, the PHONEMIZER_ESPEAK_LIBRARY environment variable is the fallback.

Done-protocol beyond /implement: verify every criterion, tick the verified checkboxes in the ticket file, append evidence under "## Comments", set Status: ready-for-human, and tell me which clips to listen to.
```

---

## Ticket 03 — Image slice (SDXL background job)

```
/implement .scratch/stickman-video-pipeline/issues/03-image-slice.md

Blocker check first: open .scratch/stickman-video-pipeline/issues/01-run-lifecycle-walking-skeleton.md and confirm its criteria are ticked; stop and tell me if not.

Before writing code, read in order: .scratch/stickman-video-pipeline/spec.md, the ticket above, CONTEXT.md and docs/adr/ (Style Prefix and Visual Bible are defined there).

Pre-agreed seams for /tdd: the tool surface with a fake ImageBackend (writes tiny PNGs, keeps a call log proving prompts and seeds). Real SDXL only in a marker-excluded smoke test, run once at the end (~7 GB one-time download).

Scope: only this ticket — the file-backed background job manager, stickman_generate_images + stickman_job_status + stickman_regenerate_image, SDXL-Lightning behind ImageBackend. No render code. Key contracts: Style Prefix + negative prompt applied server-side; batch seeds deterministic (base seed + scene id); regenerate without a seed rerolls randomly; a replacement image_prompt updates the saved Script BEFORE generating; job-start calls return immediately (well under the 30 s default tool timeout).

Environment: Windows 11; uv; RTX 3060 12GB fp16 CUDA; the repo path contains spaces — quote paths.

Done-protocol beyond /implement: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and tell me which images to eyeball.
```

---

## Ticket 04 — Render slice (Video Package)

```
/implement .scratch/stickman-video-pipeline/issues/04-render-slice.md

Blocker check first: open issues 02-narration-slice.md AND 03-image-slice.md in .scratch/stickman-video-pipeline/issues/ and confirm their criteria are ticked; stop and tell me if not.

Before writing code, read in order: .scratch/stickman-video-pipeline/spec.md, the ticket above, CONTEXT.md and docs/adr/ (the Video Package and the ADR-0001 timing rule live there).

Pre-agreed seams for /tdd: the tool surface with fake engines, but ffmpeg runs for REAL in the default suite on tiny generated fixtures (solid-color PNGs, sub-second tones); assert output duration with ffprobe within 0.35 s and SRT as exact text. Include one end-to-end default-suite test: create -> script -> narrate -> images -> render, fakes plus real ffmpeg.

Scope: only this ticket — SRT builder, ffmpeg assembly (narration track with inter-Scene gaps, still-image concat with per-Scene durations, optional looped/trimmed music bed at the configured dB), stickman_render_video as a background job, stickman_list_music, stickman_save_metadata. Key contracts: image k holds for exactly its clip duration plus the gap, hard cuts only, total = sum of durations + one gap per Scene; output 1920x1080 30fps H.264 yuv420p AAC faststart; non-16:9 images padded, never stretched.

Environment: Windows 11; uv; ffmpeg 8.1 and ffprobe on PATH; the repo path contains spaces — quote paths.

Done-protocol beyond /implement: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and tell me which rendered video to watch and what to listen for in the music mix.
```

---

## Ticket 05 — /produce-video skill + first real run

```
/implement .scratch/stickman-video-pipeline/issues/05-produce-video-skill.md

I will stay in this session — the acceptance criteria include live runs with me.

Blocker check first: open .scratch/stickman-video-pipeline/issues/04-render-slice.md and confirm its criteria are ticked; stop and tell me if not.

Before writing anything, read in order: .scratch/stickman-video-pipeline/spec.md (the workflow, Checkpoints, Yolo Mode, and metadata rules are specified there), the ticket above, CONTEXT.md and docs/adr/ (the skill must speak this vocabulary: Run, Scene, Checkpoint, Yolo Mode, Video Package).

Scope: only this ticket — the produce-video skill under .claude/skills/, the README (one-time setup incl. the MCP tool timeout raise, usage, tuning pointer), then two live verifications with me: (1) yolo smoke — I say "produce a video about <topic>, 4 scenes only, yolo, no music" and it must reach a playable MP4 + SRT + metadata with zero input from me in between; (2) default mode — it must pause at Script Approval and Image Review and act on my feedback, including regenerating one image I pick. Skill content rules from the spec: hook-first scripts of 30-45 Scenes (2-4 sentences each), Illustrative Format image prompts with NO style words, Visual Bible for recurring elements, duration warning outside 4.5-10.5 minutes, metadata with AI-generation disclosure and max-60-char title, YouTube synthetic-content declaration reminder.

Note for /tdd: this ticket is mostly skill/docs authoring plus live verification — test what is testable, don't force tests onto prose. Commit the skill and README, not the generated Run folders.

Environment: Windows 11; uv; the repo path contains spaces — quote paths.

Done-protocol beyond /implement: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and hand me the video path for the final human check.
```

---

## Ticket 06 — Channel tuning (style + voice lock)

```
/implement .scratch/stickman-video-pipeline/issues/06-channel-tuning.md

I will stay in this session — the whole point is that I pick the channel's style and voice.

Blocker check first: open issues 02-narration-slice.md AND 03-image-slice.md in .scratch/stickman-video-pipeline/issues/ and confirm their criteria are ticked; stop and tell me if not.

Before writing code, read in order: .scratch/stickman-video-pipeline/spec.md (tuning session under Implementation Decisions and Further Notes), the ticket above, CONTEXT.md (Style Prefix is a locked, channel-wide concept).

Scope: only this ticket — (1) a style-grid script: at least 4 candidate Style Prefixes x 2 sample scene prompts through the real image backend, filenames identifying each style, output to the gitignored tuning folder; (2) a voice-audition script: one sample line in at least 5 Kokoro voices, filenames identifying each voice; (3) run both, then STOP and walk me through the outputs so I pick; (4) write my picks into the channel config, prove the lock took effect per the ticket's criteria, and mark the tuning session done in the README.

Note for /tdd: the config-lock criterion is the testable part (fake-backend call log shows the new prefix); the grids themselves are real-engine one-offs, not test subjects. Commit the scripts and updated config, never the tuning outputs.

Environment: Windows 11; uv; RTX 3060 (real engines run here — expect model load time); the repo path contains spaces — quote paths.

Done-protocol beyond /implement: verify every criterion, tick the verified checkboxes, append evidence under "## Comments", set Status: ready-for-human, and confirm which style and voice are now locked.
```
