# 06 — Channel tuning: lock the Style Prefix and voice

**What to build:** The one-off branding session that turns placeholder defaults into the channel's locked identity (design decision Q16: one fixed style and voice across all videos). A style-grid script renders several candidate Style Prefixes against the same sample prompts so the creator picks a look from real outputs; a voice-audition script synthesizes one sample line in each candidate Kokoro voice so they pick by listening. The winners go into the channel config, and from then on every Run uses them automatically. Outputs land in a gitignored tuning folder.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 02 — Narration slice; 03 — Image slice.

**Status:** ready-for-agent

- [ ] The style-grid script runs to completion on this machine and writes one image per candidate-style × sample-prompt pair (at least 4 styles × 2 prompts), each filename identifying its style.
- [ ] The voice-audition script writes one WAV per candidate voice (at least 5 voices), same sample line, each filename identifying its voice.
- [ ] Tuning outputs are gitignored (`git status` stays clean after running both scripts).
- [ ] Config lock verified mechanically: after editing the config to the chosen Style Prefix, regenerating a single Scene image uses the new prefix (visible in the fake-backend call log in tests, and as a visibly restyled image in a real regeneration).
- [ ] After editing the config to the chosen voice, a fresh synthesis uses it (opt-in smoke: the produced clip is audibly the chosen voice).
- [ ] Creator sign-off recorded: the chosen style and voice are committed in the config file, and the README's tuning section marks the session done.
