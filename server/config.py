import json
import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
REFERENCE_DIR = BASE_DIR / "reference"
CAST_DIR = BASE_DIR / "reference" / "cast"
SFX_DIR = BASE_DIR / "projects" / "_sfx_cache"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
CAST_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)

_RUNTIME_API_KEY: Optional[str] = None


def set_runtime_api_key(key: str) -> None:
    global _RUNTIME_API_KEY
    cleaned = key.strip()
    if cleaned:
        _RUNTIME_API_KEY = cleaned


def get_openrouter_api_key() -> Optional[str]:
    if _RUNTIME_API_KEY:
        return _RUNTIME_API_KEY

    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key

    dotenv_path = BASE_DIR / ".env"
    if dotenv_path.exists():
        for line in dotenv_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val

    mcp_paths = [
        Path.home() / ".cursor" / "mcp.json",
        Path.home() / ".config" / "devin" / "config.json",
    ]
    for p in mcp_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                auth = (
                    data.get("mcpServers", {})
                    .get("openrouter", {})
                    .get("headers", {})
                    .get("Authorization", "")
                )
                if auth.startswith("Bearer "):
                    token = auth[7:].strip()
                    if token:
                        return token
            except Exception:
                pass

    return None


def get_key_status() -> dict:
    """Returns only a boolean indicating whether an API key is configured. Never exposes key characters or wallet balances."""
    return {"configured": bool(get_openrouter_api_key())}
