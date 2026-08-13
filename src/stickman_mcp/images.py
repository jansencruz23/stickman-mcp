"""Still images behind one swappable backend. The backend knows prompts, never Runs or Scenes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

BASE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
LIGHTNING_REPO = "ByteDance/SDXL-Lightning"
LIGHTNING_LORA = "sdxl_lightning_4step_lora.safetensors"


class ImageError(Exception):
    """The image backend could not produce a usable still."""


class ImageBackend(Protocol):
    def generate(self, prompt: str, negative_prompt: str, seed: int, destination: Path) -> None:
        """Draw prompt into destination as a PNG, reproducibly for a given seed."""


class SDXLLightningBackend:
    """SDXL base plus the 4-step Lightning LoRA, fp16 on CUDA. Weights load on first generate."""

    def __init__(self, width: int, height: int, steps: int, guidance_scale: float) -> None:
        self.width = width
        self.height = height
        self.steps = steps
        self.guidance_scale = guidance_scale
        self._pipeline: Any = None

    def generate(self, prompt: str, negative_prompt: str, seed: int, destination: Path) -> None:
        import torch

        pipeline = self._loaded()
        image = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=self.width,
            height=self.height,
            num_inference_steps=self.steps,
            guidance_scale=self.guidance_scale,
            generator=torch.Generator(device=pipeline.device).manual_seed(seed),
        ).images[0]
        image.save(destination, format="PNG")

    def _loaded(self) -> Any:
        if self._pipeline is None:
            import torch
            from diffusers import EulerDiscreteScheduler, StableDiffusionXLPipeline
            from huggingface_hub import hf_hub_download

            pipeline = StableDiffusionXLPipeline.from_pretrained(
                BASE_MODEL, torch_dtype=torch.float16, variant="fp16"
            )
            pipeline.load_lora_weights(hf_hub_download(LIGHTNING_REPO, LIGHTNING_LORA))
            pipeline.fuse_lora()
            # Lightning is distilled for trailing timesteps; the default spacing gives mush.
            pipeline.scheduler = EulerDiscreteScheduler.from_config(
                pipeline.scheduler.config, timestep_spacing="trailing"
            )
            self._pipeline = pipeline.to("cuda" if torch.cuda.is_available() else "cpu")
        return self._pipeline
