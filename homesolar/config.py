"""Settings from environment variables, plus loading of the data files."""
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTENT = ROOT / "content"


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


PROVIDERS = {
    # name: (OpenAI-compatible base URL, default model)
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.8-flash"),
    "gateway": ("https://ai-gateway.vercel.sh/v1", "google/gemini-2.5-flash"),
}


class Settings:
    @property
    def ai_provider(self) -> str:
        """'gemini' (Google AI Studio key) or 'gateway' (Vercel AI Gateway). Default: gemini if its key is set."""
        p = os.environ.get("AI_PROVIDER", "").strip().lower()
        if p in PROVIDERS:
            return p
        return "gemini" if os.environ.get("GEMINI_API_KEY") else "gateway"

    @property
    def ai_key(self) -> str:
        if self.ai_provider == "gemini":
            return os.environ.get("GEMINI_API_KEY", "")
        return os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN", "")

    @property
    def on_vercel(self) -> bool:
        return os.environ.get("VERCEL") == "1"

    @property
    def ai_enabled(self) -> bool:
        if not _flag("AI_ENABLED", True):
            return False
        if self.ai_provider == "gateway":
            # On Vercel, Python functions get the OIDC token per request (x-vercel-oidc-token header), not from env.
            return bool(self.ai_key) or self.on_vercel
        return bool(self.ai_key)

    @property
    def ai_explain_enabled(self) -> bool:
        return _flag("AI_EXPLAIN_ENABLED", False) and self.ai_enabled

    @property
    def ai_model(self) -> str:
        return os.environ.get("AI_MODEL") or PROVIDERS[self.ai_provider][1]

    @property
    def ai_base_url(self) -> str:
        return os.environ.get("AI_BASE_URL") or PROVIDERS[self.ai_provider][0]

    @property
    def ai_daily_cap(self) -> int:
        return int(os.environ.get("AI_DAILY_CAP", "50"))

    @property
    def database_url(self) -> str:
        return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL", "")

    @property
    def sharing_enabled(self) -> bool:
        return _flag("SHARING_ENABLED", True) and bool(self.database_url)


settings = Settings()


@lru_cache
def defaults() -> dict:
    return json.loads((DATA / "defaults.json").read_text(encoding="utf-8"))


@lru_cache
def regions() -> dict:
    return json.loads((DATA / "regions.json").read_text(encoding="utf-8"))


def region_map() -> dict:
    return {r["code"]: r for r in regions()["regions"]}
