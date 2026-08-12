# 02 — Narration slice: Scenes get voices (Kokoro)

**What to build:** After Script Approval, one tool call (`stickman_synthesize_narration`) turns every Scene's narration into a Narration Clip using Kokoro locally, and reports per-Scene durations plus the total — the number the creator uses to judge whether the video lands in the 5-10 minute range. Clip length *is* Scene duration (ADR-0001). The call is synchronous but resumable: Scenes that already have clips are skipped, so re-invoking after an interruption or client timeout finishes only the remainder. Kokoro hides behind the `TTSEngine` protocol — the production swap point and the test seam. Includes the espeak-ng install and the documented client-side timeout raise for this one long call.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 01 — Walking skeleton: Run lifecycle over MCP.

**Status:** ready-for-agent

- [ ] `uv run pytest` (default suite) passes using a fake engine — no model download, no GPU, no espeak-ng needed.
- [ ] With the fake engine: synthesizing a 2-Scene Run creates one WAV per Scene at the documented naming convention, and the response lists both Scenes with durations matching the fake clips within 10 ms.
- [ ] With the fake engine: a second call performs zero engine invocations (verified through the fake's call log) and still returns correct durations read from the existing files.
- [ ] Deleting one clip and re-calling synthesizes only the missing Scene.
- [ ] `stickman_get_run` after synthesis shows the audio completion count equal to the scene count.
- [ ] Opt-in smoke test (marked, excluded by default): real Kokoro synthesizes a sentence to a WAV of duration > 0.5 s at 24 kHz — proving espeak-ng and model weights are correctly installed.
- [ ] Human check on a real 2-Scene Run: both clips are audible, natural-sounding English in the configured voice.
- [ ] The response's total duration equals the sum of the per-Scene durations, and the README documents raising the MCP tool timeout for this call plus the re-invoke-to-resume behavior.
