"""Settings from environment variables, plus loading of the data files."""
import json, os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTENT = ROOT / "content"


def _flag(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    @property
    def ai_key(self) -> str:
        return os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN", "")

    @property
    def ai_enabled(self) -> bool:
        return _flag("AI_ENABLED", True) and bool(self.ai_key)

    @property
    def ai_explain_enabled(self) -> bool:
        return _flag("AI_EXPLAIN_ENABLED", False) and self.ai_enabled

    @property
    def ai_model(self) -> str:
        return os.environ.get("AI_MODEL", "google/gemini-2.5-flash")

    @property
    def ai_base_url(self) -> str:
        return os.environ.get("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1")

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
