# 04 — Render slice: the first complete Video Package

**What to build:** `stickman_render_video` runs as a background job that turns a Run with Narration Clips and images into the full Video Package: an SRT subtitle file whose cues mirror the spoken Scenes, and a 1080p30 H.264 MP4 where each Scene's image holds the screen for exactly its Narration Clip's duration plus the configured gap — hard cuts, no motion (ADR-0001 timing throughout). Optionally a music track from the curator's folder (`stickman_list_music` to choose) is looped/trimmed under the narration at the configured quiet level. `stickman_save_metadata` completes the package with title, description, and tags. With this ticket the whole pipeline is demoable end-to-end.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 02 — Narration slice; 03 — Image slice.

**Status:** ready-for-human

- [x] `uv run pytest` (default suite) passes — renders run real ffmpeg on tiny generated fixtures (no GPU, no model downloads).
- [x] End-to-end default-suite test with fake engines: create → save Script → synthesize → generate images → render completes, and `stickman_get_run` reports video_rendered true and subtitles present.
- [x] ffprobe reports the rendered MP4's duration equal to the sum of clip durations plus one gap per Scene, within 0.35 s.
- [x] ffprobe reports 1920×1080, H.264, yuv420p, 30 fps, with an AAC audio stream.
- [x] The SRT has exactly one cue per Scene, cue text equals each Scene's narration, timestamps are monotonic, and cue k starts at the sum of prior durations plus k gaps (exact-text assertion including hour rollover).
- [x] Rendering with a music track still matches the duration bound (music loops/trims to narration length, never extends it), and a human check confirms the bed is audible but clearly quieter than speech at the configured dB. *(machine half done; the listening half is left for you)*
- [x] `stickman_list_music` lists exactly the audio files present in the curated folder; naming a nonexistent track returns an `Error:` string listing what is available.
- [x] Rendering with a missing Scene image or clip returns/records an actionable error naming the Scene and the remedy tool — it does not produce a broken video.
- [x] Non-16:9 source images are letterboxed/padded, never stretched (probe the output dimensions on a deliberately square fixture).
- [x] `stickman_save_metadata` writes a file containing the title, description, and comma-joined tags, readable back; `stickman_get_run` reflects its presence.
- [ ] Human check: the MP4 plays in a normal player with narration audible and image cuts landing at narration boundaries.

## Comments

### Evidence (2026-08-16)

Built test-first at the pre-agreed seam: the tool functions called directly with the fake
`TTSEngine` and `ImageBackend`, but **ffmpeg running for real** on generated fixtures. Final
state — `uv run pytest`: **60 passed, 2 deselected in 6.24s**; `uv run mypy`: **Success: no
issues found in 22 source files**.

Nothing is asserted by inspecting the ffmpeg command we built. Every claim below is read back
off the finished MP4 with `ffprobe`, raw frame decoding, or `volumedetect`.

**Offline suite (criterion 1).** No GPU, no downloads: images are solid-colour PNGs written
with stdlib `zlib`, clips are silent WAVs written with stdlib `wave`, music is a synthesized
tone. ffmpeg and ffprobe must be on PATH — that is now in the README's setup section, since no
Python package can carry a system binary.

**Criteria 2-5, 7-10.** One test per criterion in `tests/test_render.py`:

| Criterion | Test | What it reads back |
| --- | --- | --- |
| 2 end-to-end | `test_a_topic_becomes_a_whole_video_package_without_leaving_the_tool_surface` | `scene_count == clips == images == 3`, `video_rendered`/`subtitles`/`metadata` all true |
| 3 duration | `test_the_video_lasts_every_narration_clip_plus_one_gap_per_scene` | ffprobe 2.400000 s against 2.4 expected |
| 4 format | `test_the_video_is_the_1080p30_h264_upload_format_youtube_wants` | 1920x1080, h264, yuv420p, 30/1, aac |
| 5 SRT | `test_the_subtitles_cue_every_scene_off_the_clips_that_were_actually_synthesized` plus the hour-rollover test | exact bytes; rollover asserted on the builder |
| 6 music | `test_a_short_track_loops_under_the_whole_narration_at_the_channels_quiet_level`, `test_a_track_longer_than_the_narration_is_trimmed...` | peak equals `music_level_db` within 1.5 dB, at 0 s and again at 1.5 s |
| 7 music list | `test_the_music_list_holds_the_curated_tracks_and_nothing_else_in_the_folder`, `test_naming_a_track_the_folder_does_not_have_lists_the_ones_it_does` | listing excludes a `.txt`; the error names `calm-piano.wav` |
| 8 missing assets | `test_a_scene_with_no_narration_clip...`, `test_a_scene_with_no_image...` | `Error:` names "Scene 2"/"Scene 3" and the remedy tool; no `video.mp4` |
| 9 padding | `test_a_square_image_is_padded_into_the_frame_rather_than_stretched_across_it` | frame is 1920x1080; centre pixel is the fixture, column x=20 is white pad |
| 10 metadata | `test_upload_metadata_reads_back_with_the_title_description_and_tags_ready_to_paste` | title, description, `finance, compound interest, explainer` |

Criterion 9 does more than the ticket asked: probing dimensions alone cannot tell padding from
stretching, so the test decodes a frame and checks the pillarbox column is still white while
the centre is the fixture colour. Mutation-checked — dropping
`force_original_aspect_ratio=decrease` fills that column and the test fails.

Criterion 6's machine half turned out stronger than expected: the fake narration is silence and
the music fixture is a full-scale sine, so the measured peak *is* the applied gain. It reads
-22 dB against a configured -22 dB, and still reads -22 dB at 1.5 s into a video whose music
track is only 0.6 s long — which is the loop working.

**The defect the review caught, which the criteria alone would not have.** `-t (duration + gap)`
per still made ffmpeg round every Scene **up** to a whole frame. The error is one-directional,
so it accumulates:

```
before:  cuts at 0.9333 1.8667 2.8000 3.7333   want 0.917 1.834 2.751 3.668   (drift 16 -> 65 ms)
after:   cuts at 0.9333 1.8333 2.7667 3.6667   want 0.917 1.834 2.751 3.668   (worst 16 ms)
over 20 Scenes: worst cut error 16.3 ms, and it no longer grows (was ~330 ms by Scene 20)
```

At 30-45 Scenes that was picture visibly sliding off speech — a direct breach of "image k holds
for exactly its clip duration plus the gap". Fixed by allocating frames against the running
total (`round(elapsed * fps)` boundaries) rather than per Scene. Regression test:
`test_no_cut_drifts_off_its_scene_however_ragged_the_clip_lengths_are`, which decodes every
frame and locates the cuts by colour.

Worth knowing for anyone touching this: **ffmpeg rounds `-t` to the nearest whole frame with
ties to even.** The natural fix — aim half a frame past the last frame you want — is exactly
the value that lands on the tie, and it silently produced 26 frames where 27 were planned.
`-t` must be an exact `frames / fps`.

**Real run, beyond the criteria.** The whole pipeline against real Kokoro and real SDXL, 5
Scenes, 80.5 s total:

```
clips           10.000 12.025 7.650 8.875 7.275  -> expected 47.825 s
video.mp4       47.833333 s, 1920x1080 h264 yuv420p 30/1, aac
cut check       image 1 identical at 9.50 s and 10.30 s; changes between 10.30 s and 10.50 s
                -> the cut lands at 10.4 s, where Scene 2 starts speaking, not at 10.0 s
gap 10.10-10.35 no music: -91.0 dB (digital silence) | with music: -26.9 dB peak
speech 3.0-6.0  -5.1 dB peak, both versions
```

### Decisions worth knowing

- **The gap falls *after* each Scene.** Scene k's still appears exactly when Scene k starts
  speaking, holds through its clip plus the gap, and cuts on the next Scene's first word. The
  ticket's "cue k starts at the sum of prior durations plus k gaps" reads as 0-indexed k. The
  alternative (gap first) opens the video on 0.4 s of silence and ends it the instant the last
  word stops; this way the last still gets a beat to breathe. Say the word and it flips in one
  line.
- **The narration track is joined in Python, not by ffmpeg `apad`.** stdlib `wave`,
  sample-accurate, and it halves the ffmpeg input count — 45 Scenes was heading for 90 inputs on
  one Windows command line. Clips whose channels/width/rate disagree are rejected rather than
  concatenated, because that would play one Scene at the wrong speed.
- **Pad colour is white, not black**, because the channel draws on white and a black bar beside
  a 1.75:1 white image reads as a border. Not a config knob; say so if you want one.
- **Only `video.mp4` is published by rename.** `subtitles.srt` and `narration.wav` are written
  in place on purpose: rendering is not incremental, so nothing skips them and the next call
  overwrites whatever a half-finished render left. Clips and images need `.part` precisely
  because they *are* skipped forever once present.
- **The AI disclosure line goes inside the description**, not in a section of its own — a
  separate section would be left behind when the description is copied, which defeats it.
  `metadata.py` owns the wording. **Ticket 05's skill should not add a second one.**
- **Music is addressed by name, never by path** (`music_path` rejects anything whose `.name`
  differs from the argument), so a Run cannot read outside the curated folder.
- Render reports 3 steps rather than per-Scene progress: ffmpeg is one opaque call, and parsing
  its `-progress` output would buy granularity no criterion asked for.

### From code review

Two axes ran (standards, spec). Fixed before commit:

- **The frame-drift bug above** — found by the spec axis. The most valuable finding of the
  session; the default suite missed it because the fixture durations happened to be exact
  multiples of 1/30.
- **`_staleness_warning` never mentioned the video.** Re-saving a Script left `video.mp4` and
  `subtitles.srt` from the old Script, with `stickman_get_run` still reporting them true and no
  warning — against the spec's "warns when existing derived assets become stale".
- **`stickman_get_run`'s docstring** still stopped at `video_rendered`. That docstring is the
  whole contract an MCP client sees.
- **ffmpeg was absent from the README setup**, mentioned only inside a runtime error string.
- **The music extension allowlist was too narrow**, so a curated `.aiff` was invisible and then
  reported as nonexistent. Broadened, and a file that exists in the folder but is not a readable
  format now gets its own message instead of "no such track".
- **The metadata document format lived in `runs.py`**, which is about folder layout. Moved to
  `metadata.py`, mirroring how `subtitles.py` builds and `runs.py` files.
- Style: `RENDER_STEPS` over `STEPS`, `total_seconds` and `Shot.frames` carrying their units like
  the rest of the codebase, `missing_asset_error` naming what it returns, and a `# fmt: skip`
  pragma removed (no formatter is configured in this repo).
- Found by hand, not by the review: `stickman_render_video` checked for missing assets *before*
  the running-job guard, so asking to render while the image batch was still drawing told you to
  start a second images job — which the guard would then have refused. The running-job check now
  comes first, matching `stickman_generate_images`.

Left deliberately: publish-by-rename is now duplicated a third time (`narration.py`,
`illustration.py`, `render.py`). Extracting one line across two out-of-scope modules costs more
than it buys; noted for a future cleanup.

### Left for you to check by hand

1. **Watch `projects/2026-08-16-render-check/video.mp4`** (48 s, 5 Scenes). Watch for: narration
   audible start to finish, and each image change landing on the first word of the next Scene
   rather than drifting late by the end. The last still should hold for a beat after the final
   word instead of cutting to black mid-breath. `subtitles.srt` beside it loads in VLC.
2. **Listen for the music bed in that file, and compare against `video-no-music.mp4`.** The bed
   is a placeholder pad I generated so this was judgeable — it is **not** a licensed track;
   replace it with something from the YouTube Audio Library before any real upload. What to
   listen for: the pad clearly present in the 0.4 s pauses between Scenes, and clearly *behind*
   the voice while she speaks, never competing with it. The measurement is -26.9 dB in the gaps
   against -5.1 dB peak speech. If it feels too loud or too quiet, that is one number:
   `render.music_level_db` in `channel.toml`.
3. **The images are still ticket 03's rejected style**, so ignore how they look. This check is
   about timing and sound.
4. **Restart the MCP server** so Claude Code picks up `stickman_render_video`,
   `stickman_list_music` and `stickman_save_metadata`.
