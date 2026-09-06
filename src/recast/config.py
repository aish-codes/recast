from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(os.getenv("RECAST_OUT", ROOT / "out"))
DATA_DIR = ROOT / "data"

# Your profile, and the demo fixture. Keeping these apart matters: the default
# used to point at the example, so uploading a resume overwrote the file the test
# suite depends on — and put real contact details into a tracked file.
PROFILE_DIR = DATA_DIR / "profiles"
EXAMPLE_PROFILE = PROFILE_DIR / "example.json"
DEFAULT_PROFILE = Path(os.getenv("RECAST_PROFILE", PROFILE_DIR / "me.json"))


@dataclass(frozen=True)
class Settings:
    api_key: str | None = os.getenv("RECAST_API_KEY") or os.getenv("GROQ_API_KEY")
    base_url: str = os.getenv("RECAST_BASE_URL", "https://api.groq.com/openai/v1")
    # Groq's catalog moves; check `recast models` if these 404.
    model_fast: str = os.getenv("RECAST_MODEL_FAST", "openai/gpt-oss-20b")
    model_smart: str = os.getenv("RECAST_MODEL_SMART", "openai/gpt-oss-120b")
    model_prose: str = os.getenv("RECAST_MODEL_PROSE", "openai/gpt-oss-120b")
    request_timeout: float = float(os.getenv("RECAST_TIMEOUT", "90"))
    # "low" | "medium" | "high" | "" — reasoning models only.
    reasoning_effort: str = os.getenv("RECAST_REASONING_EFFORT", "low")

    def model_for(self, task: str) -> str:
        return {"fast": self.model_fast, "smart": self.model_smart, "prose": self.model_prose}[task]


settings = Settings()
