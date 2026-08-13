# 02 — Narration slice: Scenes get voices (Kokoro)

**What to build:** After Script Approval, one tool call (`stickman_synthesize_narration`) turns every Scene's narration into a Narration Clip using Kokoro locally, and reports per-Scene durations plus the total — the number the creator uses to judge whether the video lands in the 5-10 minute range. Clip length *is* Scene duration (ADR-0001). The call is synchronous but resumable: Scenes that already have clips are skipped, so re-invoking after an interruption or client timeout finishes only the remainder. Kokoro hides behind the `TTSEngine` protocol — the production swap point and the test seam. Includes the espeak-ng install and the documented client-side timeout raise for this one long call.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 01 — Walking skeleton: Run lifecycle over MCP.

**Status:** ready-for-human

- [x] `uv run pytest` (default suite) passes using a fake engine — no model download, no GPU, no espeak-ng needed.
- [x] With the fake engine: synthesizing a 2-Scene Run creates one WAV per Scene at the documented naming convention, and the response lists both Scenes with durations matching the fake clips within 10 ms.
- [x] With the fake engine: a second call performs zero engine invocations (verified through the fake's call log) and still returns correct durations read from the existing files.
- [x] Deleting one clip and re-calling synthesizes only the missing Scene.
- [x] `stickman_get_run` after synthesis shows the audio completion count equal to the scene count.
- [x] Opt-in smoke test (marked, excluded by default): real Kokoro synthesizes a sentence to a WAV of duration > 0.5 s at 24 kHz — proving espeak-ng and model weights are correctly installed.
- [ ] Human check on a real 2-Scene Run: both clips are audible, natural-sounding English in the configured voice.
- [x] The response's total duration equals the sum of the per-Scene durations, and the README documents raising the MCP tool timeout for this call plus the re-invoke-to-resume behavior.

## Comments

### Evidence (2026-08-13)

Built test-first at the agreed seam: the tool called as a plain function with a fake `TTSEngine`
that writes silent WAVs of a duration each test chooses and logs every call. Final state —
`uv run pytest`: **28 passed, 1 deselected in 0.42s**; `uv run mypy`: **Success: no issues found
in 14 source files**; `uv run pytest -m smoke`: **1 passed**.

**Offline suite (criterion 1).** Importing the tool surface loads neither Kokoro nor torch —
`KokoroEngine` imports `kokoro` inside the call, not at module scope:

```
heavy modules loaded by the tool surface: none
```

espeak-ng is never reached in the default suite because no engine runs; the fake writes WAVs
with stdlib `wave`.

**Fake-engine behaviour (criteria 2-5, 8).** All asserted at the tool surface in
`tests/test_narration.py`, on the JSON response and the files in the Run folder:

| Criterion | Test |
| --- | --- |
| one WAV per Scene, `001.wav`/`002.wav`, durations within 10 ms | `test_every_scene_gets_a_clip_named_by_its_padded_id_with_its_own_duration` |
| second call, zero engine invocations, durations from disk | `test_calling_again_speaks_nothing_and_still_reports_the_durations_on_disk` |
| deleting one clip re-speaks only that Scene | `test_a_deleted_clip_is_the_only_one_resynthesized` |
| `stickman_get_run` audio count == scene count | `test_run_status_counts_a_clip_for_every_scene_once_narration_finishes` |
| total == sum of per-Scene durations | `test_total_duration_is_the_sum_of_the_scene_durations` |

The skip logic was mutation-tested: forcing `missing = True` in `narration.py` makes the
resume test fail with two unexpected engine calls, so the test genuinely bites.

**Real engine (criterion 6).** `tests/test_engine_smoke.py`, marked `smoke` and excluded by
`addopts = "-m 'not smoke'"`. Real Kokoro speaks the configured `af_heart` voice; the clip is
asserted > 0.5 s, 24 kHz, mono. First run 77.6 s including the ~330 MB weight download, 15.6 s
once cached.

**Live MCP session.** Launched with the `command`/`args` read out of `.mcp.json` and driven with
the official MCP client, so the tool is verified over a real stdio handshake, not only in-process:

```
configured timeout (ms): 1800000
connected: stickman_mcp 0.1.0
- stickman_synthesize_narration: Speak every Scene's Narration into a Narration Clip; a clip's
  length is its Scene's duration.

synthesize (existing run) -> {"scenes": [{"id": 1, "duration_seconds": 8.975},
                                         {"id": 2, "duration_seconds": 12.175}],
                              "total_duration_seconds": 21.15, "synthesized": 0, "skipped": 2}
unknown run               -> Error: no Run named '2026-01-01-nope'. Call stickman_create_run
                             to start one.
```

That second call skipped both Scenes from a **fresh process**, which is the disk-derived resume
working across a restart, not a cached counter.

**Measured cost, which is what sized the timeout.** RTX 3060: ~30 s one-off model load, then
**14.5 s per Scene** for 12.2 s of speech. A 30-45 Scene Script is therefore 8-12 minutes in one
call. `.mcp.json` now carries `"timeout": 1800000` (30 min), which is both the wall-clock limit
and the floor on Claude Code's stdio idle timeout — the relevant one, since this call is silent
by design.

### Decisions worth knowing

- **espeak-ng did not actually need installing.** It is installed (winget, eSpeak-NG 1.52.0), but
  `misaki/espeak.py` calls `EspeakWrapper.set_library(espeakng_loader.get_library_path())`, so
  Kokoro uses the library bundled in the `espeakng-loader` wheel that `uv sync` pulls. The README
  documents the winget install and `PHONEMIZER_ESPEAK_LIBRARY` as the fallback for when the
  bundled copy fails to load, rather than as a required step.
- **Clips publish by rename** (`001.wav.part` -> `001.wav`). Not asked for, but without it an
  interrupted write leaves a truncated WAV that the resume logic skips forever — the ticket's
  core promise would be false in exactly the case it exists for. `.part` does not match the
  `*.wav` glob, so status counts stay honest.
- **Durations are always read back off the file**, never returned by the engine, so a skipped
  Scene and a fresh one report through identical code.
- **The total is summed from the rounded per-Scene values**, so criterion 8's equality is exact
  rather than within a float tolerance.
- The response carries no 5-10 minute range warning: that rule belongs to the `/produce-video`
  skill in ticket 05, which owns the lengthen/shorten offer.

### From code review

Two review axes ran (standards, spec). Fixed before commit:

- **Only `TTSError` was caught**, so a Hugging Face download failure or a phonemizer error would
  have escaped as a raw traceback, breaking the "failures are actionable `Error:` strings"
  convention. Engine failures are now converted at the `narration` boundary.
- **A corrupt existing clip was a poison pill** — skipped on every call, so the same error
  repeated forever and the message named the wrong remedy ("fix the engine setup"). It now names
  the file and says to delete it. Both fixes were driven by failing tests first.
- **`numpy` was imported but undeclared**, arriving only transitively via Kokoro. Now a declared
  dependency.
- Style: helper grouped with its siblings, annotations back on one line, `Clip` renamed
  `NarrationClip` to match CONTEXT.md, and speculative `lang_code` / `sample_rate` parameters
  removed (the spec puts other languages out of scope).

### Left for you to check by hand

1. **Listen to the two clips** — this is the one criterion I cannot verify:

   - `projects/2026-08-13-how-compound-interest-works/audio/001.wav` (8.975 s)
   - `projects/2026-08-13-how-compound-interest-works/audio/002.wav` (12.175 s)

   Both are 24 kHz mono in `af_heart`. Listen for: audible and natural English, no clipped or
   dropped words at the start/end, and a voice you would put on the channel. If the voice is
   wrong, do not hand-tune it now — ticket 06 auditions voices properly.
2. **Restart Claude Code** so it picks up the new `stickman_synthesize_narration` tool and the
   raised `timeout` in `.mcp.json`. I had to stop the running server mid-session (it held
   `stickman-mcp.exe` open and blocked `uv sync`), so the current session's stickman tools are
   stale regardless.
3. The clip lengths (9.0 s and 12.2 s for 3-sentence Scenes) sit right in the spec's 8-15 s
   per-Scene band, so a 35-Scene Script projects to roughly 6-7 minutes — inside the 5-10 minute
   target.
