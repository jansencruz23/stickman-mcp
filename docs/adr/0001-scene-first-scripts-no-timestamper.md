# Scene-first scripts; durations come from Narration Clips

The original plan was to TTS the whole script as one mp3, run a speech-to-text timestamper over it, and derive scenes from the timestamps. We decided instead that the Script is authored as an ordered list of Scenes from the start, each Scene gets its own Narration Clip, and the clip's audio length *is* the Scene's duration. This removes an entire error-prone stage (STT/forced alignment and the drift it introduces between audio and visuals) and makes the Scene list the single source of truth for narration, images, subtitles, and timing.

## Considered Options

- Continuous TTS + forced alignment (whisperX/aeneas-style): better prosodic flow across scene boundaries, but adds a fragile stage and a second timing authority. Rejected — scene cuts mask boundary prosody anyway, and Kokoro's native word timestamps would still leave two sources of timing truth.

## Consequences

- Anything needing timing (subtitles, render, music length) reads it from the Narration Clips on disk — nothing ever transcribes audio.
- Scene boundaries are a creative decision made at script-writing time, not a signal-processing artifact.
