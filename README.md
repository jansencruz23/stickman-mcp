# Stickman MCP

A local MCP server that turns a one-line topic into a narrated stickman explainer video,
driven from a Claude Code conversation in this repo. Claude writes the Script; the tools do
the mechanical work — text-to-speech, image generation, and video assembly. Everything runs
on your own machine: no API keys, no per-video cost.

Developer-facing notes live in [docs/developing.md](docs/developing.md).

## One-time setup

Run these in order on a fresh checkout. The last step proves the whole thing works.

### 1. Python and the server

```powershell
uv sync
```

That installs everything Python, including a CUDA build of torch (~2.5 GB), Kokoro and
diffusers. Model weights are **not** bundled — the first narration downloads Kokoro-82M
(~330 MB) and the first image downloads SDXL base plus the Lightning LoRA (~7 GB) into the
Hugging Face cache. Both happen on first real use, not now.

One more download hides there: Kokoro's English front-end loads the spaCy model
`en_core_web_sm` (~12 MB) and fetches it itself if it is absent. It is not a declared
dependency, so **`uv sync` uninstalls it every time** and the next narration re-downloads it.
Harmless, but it means the first narration after any `uv sync` needs the network. To settle it
now, or to work offline:

```powershell
uv run python -m spacy download en_core_web_sm
```

### 2. ffmpeg

**ffmpeg is a separate install and must be on PATH.** No Python package can carry it, and
video assembly shells out to `ffmpeg` and `ffprobe` directly:

```powershell
winget install --id Gyan.FFmpeg -e
ffmpeg -version        # confirm PATH picked it up; restart the shell if not
```

### 3. espeak-ng, only if the smoke test says so

Kokoro phonemises English through espeak-ng. `uv sync` pulls in `espeakng-loader`, which
**bundles the library and its data**, so a separate install is not normally required —
`misaki` points phonemizer at the bundled copy on import.

Confirm with the opt-in engine test, which is excluded from the normal suite and downloads
the models:

```powershell
uv run pytest -m smoke
```

If it fails to load the library, install espeak-ng and point phonemizer at it:

```powershell
winget install --id eSpeak-NG.eSpeak-NG -e
$env:PHONEMIZER_ESPEAK_LIBRARY = "C:\Program Files\eSpeak NG\libespeak-ng.dll"
```

### 4. Raise the MCP tool timeout

`.mcp.json` registers the server project-scoped and sets a per-server `timeout` of 30
minutes. That is already committed here, but it is the one setting a different machine or a
different client will get wrong:

```json
{
  "mcpServers": {
    "stickman_mcp": {
      "command": "uv",
      "args": ["run", "--frozen", "stickman-mcp"],
      "timeout": 1800000
    }
  }
}
```

`stickman_synthesize_narration` speaks every Scene in one synchronous call — 8-12 minutes for
a full Script (see [below](#narrating-a-run-the-one-long-call)) — and the default tool timeout
in most MCP clients is 30 seconds. The number above is a hard wall-clock limit per tool call in
milliseconds, and it also raises the floor on Claude Code's idle timeout, which otherwise
aborts a stdio server's tool call after 30 minutes of silence. This call is silent by design.
Claude Code moves any call still running after two minutes into a background task, so the
session stays usable while narration runs.

Using a different MCP client? Set its tool timeout to at least 30 minutes.

### 5. Music folder

Background music is optional, and only ever comes from tracks **you** put in `music/` — which
is what keeps a monetized video clear of Content ID. The YouTube Audio Library is the easy
source. The folder is gitignored apart from its `.gitkeep`; drop `.mp3`/`.wav` files in and
they appear in `stickman_list_music()`.

### 6. Check it end to end

Restart Claude Code so it picks up `.mcp.json`, then in a conversation in this repo:

```
stickman_create_run("setup check")
stickman_get_run("<the run_id it returned>")
```

`stickman_get_run` reporting `has_script: false` and zero everything is the setup working —
the server started, loaded `channel.toml`, and created a folder under `projects/`. Delete that
folder afterwards.

## Producing a video

Say what you want:

```
produce a video about how compound interest works
```

That fires the [`/produce-video`](.claude/skills/produce-video/SKILL.md) skill, which writes a
Script, pauses at the **Script Approval** Checkpoint, narrates, warns if the video would land
outside 4.5-10.5 minutes, illustrates, pauses at the **Image Review** Checkpoint, renders, and
saves upload metadata. Each Run gets its own folder under `projects/`, holding `script.json`,
`audio/`, `images/`, `video.mp4`, `subtitles.srt` and `metadata.txt`.

Modifiers the skill listens for in that first message:

| Say | Effect |
| --- | --- |
| `yolo` | Yolo Mode: no Checkpoints, no questions, straight through to the Video Package |
| `12 scenes only` | Overrides the default 50-100 Scenes |
| `no music` / `music calm-piano.mp3` | Skips or picks the bed, instead of being asked |

Machine time for a full-length video: 8-12 minutes of narration, under a minute to render, and
images that depend on the backend. Local SDXL draws a Scene in ~2 seconds. Meta AI holds
`meta_ai.request_delay_seconds` (8 s) between Scenes on top of its own draw time, so at the current
50-100 Scenes a batch is the long pole — budget roughly 20-45 minutes and leave it running.

The rest of this file documents what each tool does, for when a Run needs driving by hand.

## Starting a Run and saving its Script

`stickman_create_run(topic)` makes the folder and returns the run id every later call takes.
`stickman_save_script(run_id, script)` then validates and persists the Scenes everything else
derives from:

```json
{
  "topic": "How compound interest works",
  "title": "Why Saving Early Beats Saving More",
  "visual_bible": {"Ana": "stickman with a short ponytail and a backpack"},
  "scenes": [
    {"id": 1, "narration": "Two friends save the same amount...", "image_prompt": "Ana stands beside a small coin jar"}
  ]
}
```

Scene ids run sequentially from 1. `visual_bible` is optional; entries are yours to repeat
verbatim in the prompts that mention them, since the server does not expand them. Image prompts
describe content only — see [the style is applied for you](#the-style-is-applied-for-you).

A failed validation returns an `Error:` naming the problem and writes nothing. A save that
invalidates work already on disk returns a `warning` listing what went stale and which tool
regenerates it — delete those files first, because those tools skip Scenes that already have
assets.

## Narrating a Run: the one long call

On an RTX 3060 `stickman_synthesize_narration` runs at roughly **1.2x the spoken length** of the
Script, plus about 30 seconds to load the model on the first call — so a 5-10 minute video takes
**8-12 minutes** whatever the Scene count. Raise the tool timeout before the first real Run
(setup step 4).

### A timeout is not a lost Run

Synthesis writes one clip per Scene as it goes and **skips Scenes that already have one**.
If the call times out, the client disconnects, or you interrupt it, just call
`stickman_synthesize_narration` again on the same run id — it picks up at the first Scene
without a clip and finishes the rest. Nothing already synthesized is redone.

The same property makes edits cheap: delete the clip for a Scene you rewrote, call the tool
again, and only that Scene is re-spoken.

The response reports each Scene's duration and the total, which is the number that tells you
whether the video lands in the target 5-10 minute range:

```json
{
  "run_id": "2026-08-13-how-compound-interest-works",
  "scenes": [
    {"id": 1, "duration_seconds": 8.975},
    {"id": 2, "duration_seconds": 12.175}
  ],
  "total_duration_seconds": 21.15,
  "synthesized": 2,
  "skipped": 0
}
```

A Scene's duration *is* its Narration Clip's length ([ADR-0001](docs/adr/0001-scene-first-scripts-no-timestamper.md)).
Nothing in this pipeline transcribes audio to recover timing.

## Illustrating a Run: a background job you poll

`stickman_generate_images` returns immediately — it starts a job and hands back the Scene
count. No timeout to worry about, unlike narration:

```json
{"run_id": "2026-08-13-how-compound-interest-works", "job": "images", "state": "running", "done": 0, "total": 40}
```

Poll `stickman_job_status` with the same run id until `state` is `done` (or `error`, which
carries the failure message). One job per Run at a time; asking for a second while one runs
returns an `Error:` pointing you back at the status tool.

On an RTX 3060 the first call spends about **40 seconds** loading SDXL, then roughly
**2 seconds per Scene** at 4 steps and 1344x768 — a 40-Scene batch lands in about two
minutes. The model stays loaded for the rest of the session, so a single
`stickman_regenerate_image` comes back in about **7 seconds**.

If a job stops halfway — a crash, a restart, an out-of-memory — call
`stickman_generate_images` again with `only_missing: true` and it draws just the Scenes
without an image. Finished images are never redrawn.

### The style is applied for you

Scene Image Prompts describe **content only**. The server prepends the channel Style Prefix
from `channel.toml` and applies the negative prompt to every image, so every frame in every
video shares one look. Seeds are `base_seed + scene_id`, so re-running a batch reproduces
the same pictures.

### Where the pixels come from: Meta AI or local SDXL

The channel draws with **Meta AI** — switched on 2026-08-20 because it matches the locked Style
Prefix and local SDXL did not. Local SDXL stays in the repo and is one line away. Change it in
`channel.toml` and restart the server:

```toml
[image]
backend = "meta-ai"   # "sdxl" draws locally on the GPU instead
```

Nothing else changes: same tools, same Run folder, same `NNN.png` files, same job polling. Only the
source of the pixels moves. Local SDXL needs no login and carries none of the risks below, so
`"sdxl"` is the fallback whenever Meta is unavailable, rate limited, or unwelcome.

**The one-time login, done by hand.** The server never sees your password. Once per machine:

```powershell
uv run playwright install chromium     # first time only
uv run python scripts/meta_login.py
```

A browser opens on meta.ai using the profile folder named by `meta_ai.profile_dir`
(`browser-profile/`, gitignored). Sign in yourself, then close the window — Meta leaves its session
in that folder and the backend reuses it. Delete the folder to sign out. If the session lapses, the
job stops with an `Error:` telling you to run the script again; it never asks for a password and
never retries into a block.

**How it behaves.** Requests go one at a time, each in a chat thread of its own, with
`meta_ai.request_delay_seconds` (8 s) held between Scenes. There is no CAPTCHA solving, no stealth
plugin and no fingerprint spoofing. If Meta shows a security check, a checkpoint or a rate limit,
the job ends in state `error` naming what Meta showed, and you deal with it in the browser yourself.

**Two risks you are accepting by switching.**

- **The account.** Meta's terms prohibit automated access to their products even while logged in, so
  the account may be checkpointed or banned. Use an account you are willing to lose, not your
  primary personal one.
- **Commercial rights.** Meta publishes no statement on commercial rights to generated output, which
  is unresolved for a monetized channel. Local SDXL carries no such question.

**What Meta cannot do that SDXL can.** It has no seed, so `stickman_regenerate_image` with an
explicit `seed` cannot reproduce an earlier picture — every request draws afresh, and rerolling
works as usual. It has no negative-prompt field, so the channel's negative prompt is appended to the
message as an `Avoid: ...` sentence instead. And it takes no size, step count or guidance, so
`image.width`, `image.height`, `image.steps` and `image.guidance_scale` reach the local backend
only. Meta picks its own size, so the Style Prefix asks for a **16:9 widescreen landscape frame**
in words instead: with that clause it returns 2048x1152 and fills the 1080p frame exactly, and
without it 1920x1280, which the render pillarboxes with 150 px of white down each side.

**Where the clause sits matters as much as whether it is there.** Left at the tail of a long prefix
it was ignored on 18 of one Run's 25 Scenes, so it now both opens and closes `style.prefix`, and
`portrait orientation, square image, tall narrow frame` sit in the negative prompt. A test asserts
the prefix still starts with `16:9`. Check a batch with
`ffprobe -v error -show_entries stream=width,height -of csv=p=0 images/001.png`: anything other
than `2048,1152` will be pillarboxed.

A browser window is visible for the whole batch, on purpose: this is your own session, not a hidden
one. Leave it alone while a job runs — a stray click lands in the chat.

### Fixing one Scene at the Image Review Checkpoint

Images land in the Run's `images/` folder as `001.png`, `002.png`, ... — open the folder and
look. For a Scene that came out badly, `stickman_regenerate_image` redraws just that one:

- **`stickman_regenerate_image(run_id, 7)`** — same prompt, new random seed. Use when the
  picture is unlucky rather than wrong. It never repeats the batch seed, so the image always
  changes.
- **`stickman_regenerate_image(run_id, 7, image_prompt="...")`** — new scene content. The
  prompt is written into `script.json` *before* the image is drawn, so the saved Script
  always explains the picture next to it.
- **`stickman_regenerate_image(run_id, 7, seed=...)`** — reproduce a specific image exactly.

## Rendering the Video Package

`stickman_render_video` is a background job like image generation: it returns at once and you
poll `stickman_job_status` until `state` is `done`. It writes three things into the Run
folder — `subtitles.srt`, `narration.wav` (the joined narration track), and `video.mp4`.

The timing rule is the whole format. Each Scene's image holds the screen for **its Narration
Clip plus the channel `scene_gap_seconds`** (0.4 s by default), hard cuts, no motion — so the
video runs for exactly the narration plus one gap per Scene, and each cut lands on the moment
the next Scene starts speaking. Subtitle cues use the same arithmetic, so captions can never
drift from the picture. Nothing transcribes audio to get there
([ADR-0001](docs/adr/0001-scene-first-scripts-no-timestamper.md)).

The output is what YouTube wants: 1920x1080, 30 fps, H.264 in yuv420p, AAC audio, `faststart`.
Images that are not 16:9 are fitted and padded with white, never stretched.

Rendering needs every Scene to have both a clip and an image. If one is missing the call
returns an `Error:` naming the Scene and the tool that fixes it, rather than starting a job
that would produce a broken video.

### Background music

```
stickman_list_music()                                  -> {"music_dir": "...", "tracks": ["calm-piano.mp3"]}
stickman_render_video(run_id, music_track="calm-piano.mp3")
```

The track is looped or trimmed to the narration's length — it can never make the video longer
— and laid under the speech at `render.music_level_db` (-22 dB by default). Naming a track the
folder does not have returns an `Error:` listing the ones it does.

### Upload metadata

`stickman_save_metadata(run_id, title, description, tags)` writes `metadata.txt` with one
section per YouTube field, ready to paste. The saved description always carries an
AI-generation disclosure line, so what you paste is compliant; tick YouTube's altered or
synthetic content box on upload as well.

`stickman_get_run` reports the package as it fills in: `video_rendered`, `subtitles` and
`metadata` are all derived from the files on disk, like every other field.

## Tuning the channel

`channel.toml` holds everything that is a channel-wide decision rather than a per-video one —
the Style Prefix every image inherits, the narration voice, the inter-Scene gap, the music
level, and the render and sampler settings. Every knob is commented in the file.

**The tuning session is done (2026-08-16).** The Style Prefix and the voice were chosen from real
outputs rather than by editing strings and hoping, and the committed values are the channel's
locked identity:

- **Style** — a flat 2D cartoon stickman in a 16:9 widescreen frame: round cream circle heads, plain
  thin black stick limbs drawn as unbroken lines, bold black outlines, flat muted colour fills. It is
  a *coloured* look, which is why `color` was removed from `style.negative_prompt`. The joint dots
  the tuning session originally picked were dropped on 2026-08-20 after seeing them on real Scenes,
  and the 16:9 clause was added the same day to stop Meta's 3:2 stills being pillarboxed.
  **Only people are stick figures** — the prefix said "stick figure characters" until 2026-08-20,
  which drew wolves as beaked stick-men and gave dogs and cats human heads on stick limbs. Animals
  are now named separately as ordinary four legged cartoon animals.
  **The drawing is meant to look hand made (2026-08-22).** "Bold clean outlines" and "cel shaded"
  gave a tidy corporate look; the prefix now asks for wobbly uneven outlines, lopsided heads, shaky
  limbs and colour painted past the lines, and `clean vector art, smooth even line weight, ruler
  straight lines, polished professional illustration, corporate flat design, airbrushed` moved into
  the negative prompt. Crude is the channel's identity, not a defect to fix.
- **Cuts** — `render.scene_gap_seconds` went 0.4 to 0.2 on 2026-08-20: at 0.4 the gap between one
  Scene's last word and the next read as dead air rather than a beat.
- **Voice** — `am_puck` at `voice.speed = 1.15`.

`tests/test_channel_config.py` asserts these exact values, so changing them is a deliberate
channel decision that updates a test, not a passing edit.

### Re-running the tuning session

```
uv run python scripts/style_grid.py [--guidance 3.0]     # candidate prefixes x sample prompts
uv run python scripts/voice_audition.py                  # one line in each candidate voice
```

Both write into the gitignored `tuning/` folder, foldered by the setting that varies, so a second
pass never overwrites the grid you are comparing against. Edit the candidate list at the top of
either script, run it, look or listen, then move the winner into `channel.toml`.

Two things the grids taught, worth knowing before you re-run them:

- **The negative prompt does nothing at `image.guidance_scale = 1.0`.** diffusers only runs
  classifier-free guidance above 1.0, and SDXL-Lightning is distilled to be used without it.
  Raising guidance to 3.0 makes it bite, at roughly double the time per image.
- **Kokoro's `speed` is not a linear time scale.** 1.15 measures about 1.07x faster and 1.25 about
  1.18x, so pick the number by measuring a clip, not by arithmetic.

Two other knobs worth knowing: `render.music_level_db` if the bed sits too loud or too quiet under
the speech, and `render.scene_gap_seconds` if the cuts feel rushed.
