"""Run folders: one self-contained directory per production, status derived from disk."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .script import Script, ScriptError, parse_script, script_to_dict

AUDIO_DIR = "audio"
IMAGES_DIR = "images"
SCRIPT_FILE = "script.json"
VIDEO_FILE = "video.mp4"
MAX_SLUG_LENGTH = 48


class RunStore:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    def path(self, run_id: str) -> Path:
        return self.projects_dir / run_id

    def exists(self, run_id: str) -> bool:
        return self.path(run_id).is_dir()

    def save_script(self, run_id: str, script: Script) -> None:
        text = json.dumps(script_to_dict(script), indent=2)
        (self.path(run_id) / SCRIPT_FILE).write_text(text, encoding="utf-8")

    def status(self, run_id: str) -> dict[str, Any]:
        """Every field is read from disk, so an interrupted Run reports the truth on restart."""
        script = self.load_script(run_id)
        return {
            "run_id": run_id,
            "path": str(self.path(run_id)),
            "has_script": script is not None,
            "scene_count": len(script.scenes) if script else 0,
            "narration_clips": self.narration_clip_count(run_id),
            "images": self.image_count(run_id),
            "video_rendered": (self.path(run_id) / VIDEO_FILE).is_file(),
        }

    def narration_clip_path(self, run_id: str, scene_id: int) -> Path:
        return self.path(run_id) / AUDIO_DIR / f"{scene_id:03d}.wav"

    def narration_clip_count(self, run_id: str) -> int:
        return len(list((self.path(run_id) / AUDIO_DIR).glob("*.wav")))

    def image_count(self, run_id: str) -> int:
        return len(list((self.path(run_id) / IMAGES_DIR).glob("*.png")))

    def load_script(self, run_id: str) -> Script | None:
        source = self.path(run_id) / SCRIPT_FILE
        if not source.is_file():
            return None
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScriptError(f"{source} could not be read: {exc}.") from None
        return parse_script(data)

    def create(self, topic: str, slug: str | None = None) -> str:
        base = f"{date.today():%Y-%m-%d}-{slugify(slug or topic)}"
        run_id, attempt = base, 1
        while self.path(run_id).exists():
            attempt += 1
            run_id = f"{base}-{attempt}"
        (self.path(run_id) / AUDIO_DIR).mkdir(parents=True)
        (self.path(run_id) / IMAGES_DIR).mkdir(parents=True)
        return run_id


def slugify(text: str) -> str:
    slug = "-".join(re.findall(r"[a-z0-9]+", text.lower()))[:MAX_SLUG_LENGTH]
    return slug.rstrip("-") or "run"
