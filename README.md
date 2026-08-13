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

That installs everything, including a CUDA build of torch (~2.5 GB) and Kokoro. Model
weights are **not** bundled — the first narration downloads Kokoro-82M (~330 MB) into the
Hugging Face cache. Later tickets add SDXL (~7 GB).

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
