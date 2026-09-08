"""Drive a Run on any channel. The MCP server is pinned to channel one, so anything else runs here.

    python scripts/channel_run.py create   --channel channel-anime.toml --script debt.json --slug how-600-became-8400
    python scripts/channel_run.py audition --channel channel-anime.toml --sheet "a character sheet of ..."
    python scripts/channel_run.py choose   --channel channel-anime.toml --candidate 2
    python scripts/channel_run.py narrate  --channel channel-anime.toml
    python scripts/channel_run.py images   --channel channel-anime.toml [--only-missing]
    python scripts/channel_run.py render   --channel channel-anime.toml [--music quiet-dread.wav]
    python scripts/channel_run.py metadata --channel channel-anime.toml --meta metadata.json
    python scripts/channel_run.py status   --channel channel-anime.toml

The run id is remembered per channel in scripts/run-id-<channel>.txt, so two channels never collide.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
os.chdir(REPO)

# The channel decides the config, and the config is read the moment stickman_mcp is imported.
_parser = argparse.ArgumentParser(description="Drive a Run on a chosen channel.")
_parser.add_argument("command")
_parser.add_argument("--channel", default="channel.toml")
_parser.add_argument("--script", default="script.json", help="script file in scripts/, for create and save")
_parser.add_argument("--meta", default="metadata.json", help="metadata file in scripts/, for metadata")
_parser.add_argument("--slug", help="folder name override; defaults to a slug of the topic")
_parser.add_argument("--sheet", help="Lead sheet prompt, for audition")
_parser.add_argument("--candidates", type=int, default=4, help="how many Lead candidates to draw")
_parser.add_argument("--candidate", type=int, help="which Lead candidate to keep, for choose")
_parser.add_argument("--music", help="track file name from the music folder, for render")
_parser.add_argument("--only-missing", action="store_true", help="images: draw only the Scenes without one")
_options = _parser.parse_args()
os.environ["STICKMAN_CHANNEL_CONFIG"] = str(REPO / _options.channel)

import shutil  # noqa: E402

from stickman_mcp.config import load_channel_config  # noqa: E402
from stickman_mcp.illustration import audition_lead, backend_for, generate_images  # noqa: E402
from stickman_mcp.metadata import build_metadata  # noqa: E402
from stickman_mcp.narration import synthesize  # noqa: E402
from stickman_mcp.render import music_path, render  # noqa: E402
from stickman_mcp.runs import RunStore  # noqa: E402
from stickman_mcp.script import parse_script  # noqa: E402
from stickman_mcp.tts import KokoroEngine  # noqa: E402

CONFIG = load_channel_config()
RUNS = RunStore(CONFIG.projects_dir)
STATE = HERE / f"run-id-{Path(_options.channel).stem}.txt"


def run_id() -> str:
    return STATE.read_text(encoding="utf-8").strip()


def script():
    loaded = RUNS.load_script(run_id())
    assert loaded is not None, f"{run_id()} has no saved Script"
    return loaded


def cmd_create() -> None:
    payload = json.loads((HERE / _options.script).read_text(encoding="utf-8"))
    parsed = parse_script(payload)  # parsed before the folder exists, so a bad Script creates nothing
    rid = RUNS.create(payload["topic"], slug=_options.slug)
    STATE.write_text(rid, encoding="utf-8")
    RUNS.save_script(rid, parsed)
    print(f"run_id={rid}\npath={RUNS.path(rid)}\nscenes={len(parsed.scenes)}\nformat={parsed.format}")


def cmd_save() -> None:
    """Re-save the script file into the existing Run, for an edit made after create."""
    parsed = parse_script(json.loads((HERE / _options.script).read_text(encoding="utf-8")))
    RUNS.save_script(run_id(), parsed)
    print(f"saved scenes={len(parsed.scenes)}")


def cmd_audition() -> None:
    assert _options.sheet, "--sheet is required: describe the character and the sheet layout"
    for candidate in audition_lead(RUNS, run_id(), _options.sheet, _options.candidates, backend_for(CONFIG), CONFIG):
        print(f"drew candidate {candidate}", flush=True)
    print(f"candidates in {RUNS.path(run_id()) / 'reference'}")


def cmd_choose() -> None:
    assert _options.candidate, "--candidate is required"
    source = RUNS.lead_candidate_path(run_id(), _options.candidate)
    assert source.is_file(), f"no candidate {_options.candidate}; have {[p.name for p in RUNS.lead_candidates(run_id())]}"
    shutil.copyfile(source, RUNS.lead_path(run_id()))
    print(f"lead={RUNS.lead_path(run_id())}")


def cmd_narrate() -> None:
    clips = synthesize(RUNS, run_id(), script(), KokoroEngine(), CONFIG.voice, CONFIG.voice_speed)
    total = sum(clip.duration_seconds for clip in clips)
    fresh = sum(1 for clip in clips if clip.synthesized)
    print(f"clips={len(clips)} synthesized={fresh} skipped={len(clips) - fresh}")
    print(f"total_seconds={total:.1f} runtime={int(total // 60)}:{int(total % 60):02d}")


def cmd_images() -> None:
    for scene_id in generate_images(RUNS, run_id(), script(), backend_for(CONFIG), CONFIG, _options.only_missing):
        print(f"drew {scene_id}", flush=True)


def cmd_render() -> None:
    music = music_path(CONFIG, _options.music) if _options.music else None
    for step in render(RUNS, run_id(), script(), CONFIG, music):
        print(f"step {step}", flush=True)
    print(f"video={RUNS.video_path(run_id())}")


def cmd_metadata() -> None:
    meta = json.loads((HERE / _options.meta).read_text(encoding="utf-8"))
    RUNS.save_metadata(run_id(), build_metadata(meta["title"], meta["description"], meta["tags"]))
    print(f"metadata={RUNS.metadata_path(run_id())}")


def cmd_status() -> None:
    print(json.dumps(RUNS.status(run_id()), indent=2, default=str))


if __name__ == "__main__":
    globals()[f"cmd_{_options.command}"]()
