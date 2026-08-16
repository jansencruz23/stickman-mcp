# 05 — /produce-video skill and the first real topic-to-video run

**What to build:** The conversation workflow that makes the tools a product. A `/produce-video` skill instructs Claude to: write a retention-oriented Script (hook first, 30-45 Scenes of 2-4 sentences, Illustrative Format image prompts with no style words, Visual Bible for recurring elements), pause at the Script Approval and Image Review Checkpoints (skipped in Yolo Mode), drive the tool sequence with job polling and duration warnings (offer to lengthen/shorten outside 4.5-10.5 minutes), handle music selection, and finish with metadata that always includes an AI-generation disclosure plus the reminder to tick YouTube's synthetic-content declaration. A README documents one-time setup (uv sync, espeak-ng, timeout raise, model downloads, music folder). Acceptance is a real production smoke run.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 04 — Render slice.

**Status:** ready-for-human

- [x] The skill is listed/invocable in a fresh Claude Code session in this repo.
- [x] Real smoke run, Yolo Mode: a single message ("produce a video about <topic>, 4 scenes only, yolo, no music") yields a Run folder containing a playable MP4, an SRT, and metadata — with no human input between the message and the deliverables.
- [x] Real run, default mode: the workflow stops and waits at Script Approval (script shown scene-by-scene) and again at Image Review (images folder named, regeneration offered) — verified by observing both pauses in conversation.
- [x] During Image Review, regenerating one Scene by id visibly replaces that image and no others, and the re-rendered video uses the replacement.
- [x] The saved metadata contains the AI-generation disclosure line, a title of at most 60 characters, and 10-15 tags.
- [x] The skill's duration rule fires: a deliberately short test Script triggers the lengthen/shorten offer before rendering.
- [x] README setup section verified by execution on this machine: following it top-to-bottom on a clean checkout reaches a working `stickman_get_run` call (documented timeout raise included).
- [ ] Human check of the smoke video: narration matches the Script, images match their Scenes' prompts, cuts land at narration boundaries, style is consistent across Scenes.

## Comments

### Evidence (2026-08-16)

Two live Runs with the creator in the session, one per mode. `uv run pytest`: **64 passed, 2
deselected in 5.29s**; `uv run mypy`: **Success: no issues found in 23 source files**.

**Criterion 1.** A separate headless process, not this session: `claude -p "List only the names of
skills available to you that relate to producing videos."` answered `produce-video`.

**Criterion 2 — Yolo Mode, `projects/2026-08-16-why-your-phone-battery-dies-faster-in-the-cold/`.**
The creator's single message was "go pick a topic" against a standing "4 scenes only, yolo, no
music". Zero input between that and the deliverables: no Checkpoint fired, no music question, no
duration stop.

```
narration      9.400 13.625 12.600 12.600  -> 48.225 s
video.mp4      49.833333 s against 48.225 + 4*0.4 = 49.825 expected   (8 ms)
               1920x1080 h264 30/1 aac
subtitles.srt  4 cues, 00:00:00,000 -> 00:00:49,425
metadata.txt   title 38 chars, 13 tags, disclosure line present once
```

**Criteria 3, 4, 6 — default mode, `projects/2026-08-16-why-dogs-became-companions/`.** Eight
Scenes on why dogs became companions. The workflow stopped and waited **three** times, each pause
acted on:

| Pause | What was shown | Creator's answer |
| --- | --- | --- |
| Script Approval | title, Visual Bible, all 8 Scenes with id + narration + Image Prompt, estimated duration; nothing saved yet | "approve" |
| Duration offer | 100.5 s, named as below the 4.5 min floor, with lengthen / shorten / proceed costed | "proceed as is" |
| Image Review | `images/` named, `001.png`-`008.png` mapped to Scenes, both regeneration forms offered | picked Scene 5 |

Criterion 6 fired on a real Script rather than a contrived one — 8 Scenes lands at 1:41, under the
floor, and the offer quoted the ~22 extra Scenes needed to reach 4.5 minutes.

**Criterion 4 measured, not eyeballed.** All eight images were md5'd either side of
`stickman_regenerate_image(run_id, 5)`:

```
005.png  3eb6c0ba4590adb16aa2eb3aa2e0cfd8 -> 2755d71fdb13a9a7f61ff097d699350e
the other seven  byte-identical
seed 1052373909  (a reroll; the batch seed for Scene 5 would be 20260818)
script_updated false
```

Then the re-rendered video was probed at 55.0 s, mid-Scene-5 (Scene 5 starts at 48.625 s = four
clips plus four gaps): the decoded frame is the replacement image, letterboxed. The SRT agrees —
cue 5 starts at `00:00:48,625`. Video 103.733333 s against 103.725 expected.

**Criterion 5.** Both Runs: disclosure line present exactly once (`grep -c` = 1) and inside the
description, per ticket 04's decision that `metadata.py` owns the wording — the skill is written to
*not* add its own. Titles 38 and 41 characters. Tags 13 and 14.

**Criterion 7.** Executed top to bottom on this machine, in order: `uv sync`; `ffmpeg -version` and
`ffprobe -version` (8.1); `uv run pytest -m smoke` (**2 passed in 45.66s**, both real engines);
`.mcp.json` timeout confirmed at 1800000; music folder listed; then `stickman_create_run("setup
check")` and `stickman_get_run` returning `has_script: false` with zeros — which is exactly what the
README says success looks like. Folder deleted afterwards, as the README instructs.

### Two defects the work surfaced

- **`uv sync` uninstalls `en_core_web_sm`.** Kokoro's English front-end (`misaki/en.py:500`) calls
  `spacy.cli.download` when the model is absent, so the first narration after any `uv sync` silently
  needs the network. Not a declared dependency, so `uv` prunes it every time. Now in the README with
  the command to pre-seed it. Found only by running the setup rather than reading it.
- **The README never documented `stickman_save_script`** — the one tool whose payload is not
  obvious. Caught by the new test, not by review.

### From code review

Two axes ran (standards, spec). Fixed before commit:

- **The duration rule's remedy was a no-op.** It said "re-save plus re-synthesize only the Scenes
  that changed", but `narration.py:25` skips any Scene whose clip already exists, so an edited Scene
  would have kept its **old audio** — and the shorten branch is worse, because cutting a Scene
  renumbers everything after it and leaves clips and images present but attached to the wrong Scene,
  which renders without complaint. The rule now leads with deleting `audio/<id>.wav` and
  `images/<id>.png` before regenerating. This is the finding that would have bitten a real
  lengthen/shorten.
- **Polling ignored the error state.** "until `state` is `done`" loops forever on a failed job,
  since a failure never reaches `done`. Now polls until `state` leaves `running` and routes `error`
  to the recovery section.
- **The Scene-count arithmetic contradicted itself** — "30-45 Scenes" for "5-10 minutes" at
  "roughly 11 seconds per Scene" tops out at 8.25 minutes. Replaced with 12 s, which is what the two
  real Runs measured (12.06 and 12.57 s per Scene) and which puts 30-45 Scenes at 6-9 minutes.
- **The duration rule measured the narration, not the video.** The video is narration plus one gap
  per Scene, which at 30-45 Scenes is 12-18 s the rule was ignoring.
- The Script's saved shape is now named in the skill, so Scenes are authored with the right field
  names instead of being corrected by a validation error.
- README: the tuning section carried a `.scratch/` ticket path and a "not done yet" status that
  would rot; it now states the placeholder situation without the ticket reference.

Declined, with reasons: splitting `The two Checkpoints` and `When a stage stops` into sibling files.
Checkpoints are on the common path of every default-mode Run, and a recovery section that fails to
load at the moment a job errors is worse than fifteen inline lines.

### Left for you to check by hand

1. **Watch `projects/2026-08-16-why-your-phone-battery-dies-faster-in-the-cold/video.mp4`** (50 s).
   Narration against the Script, cuts landing on first words, subtitles in step.
2. **The images are still the placeholder Style Prefix.** Scene 5's reroll in the dogs Run came back
   as a detailed pen-and-ink wolf, and dropped the arrows and the caged fox the prompt asked for —
   style *and* prompt adherence both belong to ticket 06, not here. Judge the workflow, not the art.
3. The dogs Run is 1:41, deliberately short. Neither Run is channel-length; the first full 30-45
   Scene Run is worth doing once the style is locked.
