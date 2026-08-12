# 04 — Render slice: the first complete Video Package

**What to build:** `stickman_render_video` runs as a background job that turns a Run with Narration Clips and images into the full Video Package: an SRT subtitle file whose cues mirror the spoken Scenes, and a 1080p30 H.264 MP4 where each Scene's image holds the screen for exactly its Narration Clip's duration plus the configured gap — hard cuts, no motion (ADR-0001 timing throughout). Optionally a music track from the curator's folder (`stickman_list_music` to choose) is looped/trimmed under the narration at the configured quiet level. `stickman_save_metadata` completes the package with title, description, and tags. With this ticket the whole pipeline is demoable end-to-end.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 02 — Narration slice; 03 — Image slice.

**Status:** ready-for-agent

- [ ] `uv run pytest` (default suite) passes — renders run real ffmpeg on tiny generated fixtures (no GPU, no model downloads).
- [ ] End-to-end default-suite test with fake engines: create → save Script → synthesize → generate images → render completes, and `stickman_get_run` reports video_rendered true and subtitles present.
- [ ] ffprobe reports the rendered MP4's duration equal to the sum of clip durations plus one gap per Scene, within 0.35 s.
- [ ] ffprobe reports 1920×1080, H.264, yuv420p, 30 fps, with an AAC audio stream.
- [ ] The SRT has exactly one cue per Scene, cue text equals each Scene's narration, timestamps are monotonic, and cue k starts at the sum of prior durations plus k gaps (exact-text assertion including hour rollover).
- [ ] Rendering with a music track still matches the duration bound (music loops/trims to narration length, never extends it), and a human check confirms the bed is audible but clearly quieter than speech at the configured dB.
- [ ] `stickman_list_music` lists exactly the audio files present in the curated folder; naming a nonexistent track returns an `Error:` string listing what is available.
- [ ] Rendering with a missing Scene image or clip returns/records an actionable error naming the Scene and the remedy tool — it does not produce a broken video.
- [ ] Non-16:9 source images are letterboxed/padded, never stretched (probe the output dimensions on a deliberately square fixture).
- [ ] `stickman_save_metadata` writes a file containing the title, description, and comma-joined tags, readable back; `stickman_get_run` reflects its presence.
- [ ] Human check: the MP4 plays in a normal player with narration audible and image cuts landing at narration boundaries.
