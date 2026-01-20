import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Set


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value is not None else default


def _parse_api_keys(raw: str | None) -> Dict[str, Set[str]]:
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("API_KEYS_JSON must be a JSON object")
    parsed: Dict[str, Set[str]] = {}
    for key, tenants in data.items():
        if not isinstance(tenants, list):
            raise ValueError("API_KEYS_JSON values must be lists")
        parsed[str(key)] = {str(tenant) for tenant in tenants}
    return parsed


@dataclass(frozen=True)
class Settings:
    db_path: str
    api_keys: Dict[str, Set[str]]
    max_title_len: int
    max_content_len: int
    max_tags: int
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    db_path = _get_env("DB_PATH", "./data/app.db")
    api_keys_json = _get_env("API_KEYS_JSON")
    max_title_len = int(_get_env("MAX_TITLE_LEN", "200"))
    max_content_len = int(_get_env("MAX_CONTENT_LEN", "200000"))
    max_tags = int(_get_env("MAX_TAGS", "20"))
    log_level = _get_env("LOG_LEVEL", "INFO")

    return Settings(
        db_path=db_path,
        api_keys=_parse_api_keys(api_keys_json),
        max_title_len=max_title_len,
        max_content_len=max_content_len,
        max_tags=max_tags,
        log_level=log_level,
    )

