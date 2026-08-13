# Stickman MCP

A local MCP server that turns a one-line topic into a narrated stickman explainer video,
driven from a Claude Code conversation in this repo. Claude writes the Script; the tools do
the mechanical work — text-to-speech, image generation, and video assembly. Everything runs
on your own machine: no API keys, no per-video cost.

The full `/produce-video` walkthrough is ticket 05's deliverable. What follows is the setup
and the tool behaviour that exists today. Developer-facing notes live in
[docs/developing.md](docs/developing.md).

## One-time setup

```powershell
uv sync
```

That installs everything, including a CUDA build of torch (~2.5 GB), Kokoro and diffusers.
Model weights are **not** bundled — the first narration downloads Kokoro-82M (~330 MB) and
the first image downloads SDXL base plus the Lightning LoRA (~7 GB) into the Hugging Face
cache.

Confirm the install with the opt-in engine smoke test, which is excluded from the normal
suite:

```powershell
uv run pytest -m smoke
```

### espeak-ng

Kokoro phonemises English through espeak-ng. `uv sync` pulls in `espeakng-loader`, which
**bundles the library and its data**, so a separate install is not normally required —
`misaki` points phonemizer at the bundled copy on import.

If the bundled library fails to load on your machine, install espeak-ng and point
phonemizer at it:

```powershell
winget install --id eSpeak-NG.eSpeak-NG -e
$env:PHONEMIZER_ESPEAK_LIBRARY = "C:\Program Files\eSpeak NG\libespeak-ng.dll"
```

The smoke test above is what tells you which situation you are in.

## Narrating a Run: the one long call

`stickman_synthesize_narration` speaks every Scene in one synchronous call. On an RTX 3060
it runs at roughly **14.5 seconds per Scene**, plus about 30 seconds to load the model on
the first call — so a full 30-45 Scene Script takes **8-12 minutes**.

### Raise the tool timeout

`.mcp.json` sets a per-server `timeout` of 30 minutes for exactly this call:

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

That number is a hard wall-clock limit per tool call in milliseconds, and it also raises the
floor on Claude Code's idle timeout — which otherwise aborts a stdio server's tool call after
30 minutes of silence, and this call is silent by design. Claude Code moves any call still
running after two minutes into a background task, so the session stays usable while narration
runs.

Using a different MCP client? Set its tool timeout to at least 30 minutes; several clients
still default to 30 seconds.

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
