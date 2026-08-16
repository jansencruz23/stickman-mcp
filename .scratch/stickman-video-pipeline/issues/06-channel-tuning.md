# 06 — Channel tuning: lock the Style Prefix and voice

**What to build:** The one-off branding session that turns placeholder defaults into the channel's locked identity (design decision Q16: one fixed style and voice across all videos). A style-grid script renders several candidate Style Prefixes against the same sample prompts so the creator picks a look from real outputs; a voice-audition script synthesizes one sample line in each candidate Kokoro voice so they pick by listening. The winners go into the channel config, and from then on every Run uses them automatically. Outputs land in a gitignored tuning folder.

Spec: `.scratch/stickman-video-pipeline/spec.md`

**Blocked by:** 02 — Narration slice; 03 — Image slice.

**Status:** ready-for-human

- [x] The style-grid script runs to completion on this machine and writes one image per candidate-style × sample-prompt pair (at least 4 styles × 2 prompts), each filename identifying its style.
- [x] The voice-audition script writes one WAV per candidate voice (at least 5 voices), same sample line, each filename identifying its voice.
- [x] Tuning outputs are gitignored (`git status` stays clean after running both scripts).
- [x] Config lock verified mechanically: after editing the config to the chosen Style Prefix, regenerating a single Scene image uses the new prefix (visible in the fake-backend call log in tests, and as a visibly restyled image in a real regeneration).
- [ ] After editing the config to the chosen voice, a fresh synthesis uses it (opt-in smoke: the produced clip is audibly the chosen voice).
- [x] Creator sign-off recorded: the chosen style and voice are committed in the config file, and the README's tuning section marks the session done.

## Comments

### Evidence (2026-08-16)

The creator sat in the session and made both picks themselves, which is the point of the ticket.
Final state — `uv run pytest`: **67 passed, 2 deselected in 5.11s**; `uv run mypy`: **Success: no
issues found in 25 source files** (`scripts` added to the mypy scope); `uv run pytest -m smoke`:
**2 passed in 38.18s**.

**What is now locked in `channel.toml`:**

| Setting | Value |
| --- | --- |
| `style.prefix` | flat 2d cartoon, round cream circle heads, thin black stick limbs with joint dots, bold black outlines, flat muted colour fills |
| `style.negative_prompt` | unchanged except `color`, which was **removed** |
| `voice.name` | `am_puck` |
| `voice.speed` | `1.15` |
| `image.guidance_scale` | `1.0`, unchanged — creator declined, since the backend is being replaced (ticket 07) |

**The grids (criteria 1-3).** `scripts/style_grid.py` rendered 7 prefixes (6 candidates plus the
then-current one as a control) x 2 subjects, twice — `tuning/style-grid/guidance-1.0/` and
`guidance-3.0/`, 28 images, each named `<style>--<subject>.png` with a `styles.txt` legend.
`scripts/voice_audition.py` spoke one 3-sentence line in 8 voices, twice —
`tuning/voice-audition/speed-1.0/` and `speed-1.15/`, 16 WAVs named `<voice>.wav`. `git status`
lists none of it; `tuning/` was already gitignored.

**The config lock (criterion 4).** Built red-first at the agreed seam:

| Test | Proves |
| --- | --- |
| `test_the_shipped_config_carries_the_locked_channel_identity` | the shipped `channel.toml` holds the locked prefix, `am_puck`, `1.15`, and no colour term in the negatives |
| `test_regenerating_a_scene_draws_it_in_the_locked_channel_style` | regeneration passes that config's prefix and negatives to the backend, read off the fake's call log |
| `test_every_scene_is_spoken_in_the_channel_voice_at_the_channel_speed` | both voice and speed reach the engine on every Scene |

The first and third were genuinely red before the change. The second was green on arrival (the
config was already locked by then and the regeneration path predates this ticket), so it was
mutation-tested instead: forcing `compose_prompt` to return `f"MUTANT {scene.image_prompt}"` fails
it. The `locked_channel` fixture copies the **shipped** config into `tmp_path`, so relative paths
redirect to a throwaway Run folder while the values under test stay the real ones.

Real regeneration through the tool surface, same Run as ticket 03:

```
style prefix in force: flat 2d cartoon illustration, stick figure characters with b ...
negative prompt: photorealistic, 3d render, photograph, text, watermark, signature, blurry,
                 extra limbs, cluttered background
voice / speed: am_puck 1.15
regenerate -> seed 782314186, script_updated false
```

Before and after are kept in the gitignored `tuning/lock-proof/`. The before is a filled monochrome
silhouette on white; the after is outlined cartoon figures — visibly restyled. **Adherence varies by
seed**: an earlier reroll came out strongly coloured, this one nearly monochrome. The prefix reaches
the model reliably; SDXL following it does not. That is the ticket-07 problem, not this one.

### Decisions worth knowing

- **`voice.speed` is a new config setting and a new `TTSEngine` parameter.** The creator asked for
  am_puck "like 1.15x faster", so rate is part of the locked audio identity and belongs in the one
  channel config the spec describes. `speed` is passed per call, next to `voice`, because that is
  Kokoro's own API shape and it makes the value observable in the fake's call log.
- **Kokoro's `speed` is not a linear time scale.** Measured on am_puck, same line: 1.0 -> 13.35 s,
  1.15 -> 12.43 s (**1.07x**), 1.25 -> 11.32 s (1.18x), 1.35 -> 9.43 s (1.42x). `1.15` ships because
  that is the number the creator named; a true 1.15x rate would be about **1.22**. Recorded in the
  config comment and the README so nobody recomputes it.
- **The negative prompt is inert at `guidance_scale = 1.0`** (ticket 03 established this; diffusers
  only runs classifier-free guidance above 1.0). Only `color` was removed — the term directly
  contradicted the coloured look the creator picked.
- **The candidate list in `style_grid.py` is the 2026-08-16 audition set, all rejected.** It is kept
  as the record of what was tried; the script always renders the locked prefix as `current`, so a
  re-run compares alternatives against what is live.
- The Kokoro smoke test now writes `projects/smoke/kokoro-am_puck.wav` instead of a temp dir, so
  criterion 5 is something a human can actually listen to. It follows the SDXL smoke test's existing
  convention.

### From code review

Two axes ran (standards, spec). Both independently flagged the same defect, which is why it was
fixed rather than argued:

- **Three unrequested terms had been added to the negative prompt** (`gradient, soft shading,
  realistic anatomy`). They were outside the ticket, and provably inert at guidance 1.0, so they
  would have shipped unvalidated. Reverted — the original list minus `color` is already coherent
  with the locked look.
- The `--guidance 2.5` in the script docstring contradicted the README's `3.0`.
- `locked_channel` duplicated `channel`'s three setup lines; extracted.
- `test_images.py` asserted against a hardcoded constant on one line and the config on the next.
  Now consistently config-derived, with the literal lock living only in `test_channel_config.py`.
- `PROMPTS` was renamed `SUBJECTS`: CONTEXT.md reserves Image Prompt for the string that *carries*
  the Style Prefix, and those values are Scene content.
- The colour guard now catches `colour` as well as `color`.

Declined, with reasons: a `Voice(name, speed)` value type (real Data Clump, but `ImageBackend.generate`
already passes its config-derived arguments separately — introducing a value type on one engine seam
only would make the two inconsistent); a default of `speed = 1.0` on the protocol (there is one
production implementer and one fake, both updated, and a default would let a new engine silently drop
the channel's locked rate); moving smoke output to `tuning/` (ticket 03's documented convention); and
an upper bound on `voice.speed` (the config reader has no maximum concept for any setting).

The spec axis also reported that the SDXL smoke test was relocated to `projects/smoke/` in this
change. It was not — it has written there since ticket 03; only the Kokoro one moved.

### Left for you to check by hand

1. **Listen to `projects/smoke/kokoro-am_puck.wav`** — criterion 5's "audibly the chosen voice" is
   the one thing I cannot verify, so it stays unticked. The mechanical half is proven by
   `test_every_scene_is_spoken_in_the_channel_voice_at_the_channel_speed`.
2. **Decide on the speed number.** `1.15` is what you asked for and what shipped; `1.22` is what a
   real 1.15x rate needs. Re-auditioned clips at the locked rate are in
   `tuning/voice-audition/speed-1.15/`.
3. **Restart the MCP server** so it picks up the locked config and the new `voice.speed`. The
   registered server holds `stickman-mcp.exe` open, so `uv run` was used with `--no-sync` throughout
   rather than stopping it mid-session.
