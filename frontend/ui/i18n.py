import json
import os
from pathlib import Path


class I18n:
    """Loader dan accessor untuk string UI multi-bahasa."""

    def __init__(self, lang: str = "en"):
        self._data = {}
        self._lang = lang
        self.load(lang)

    def load(self, lang: str):
        self._lang = lang
        base = Path(os.path.dirname(os.path.abspath(__file__))) / "i18n"
        path = base / f"{lang}.json"
        fallback = base / "en.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            with open(fallback, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def t(self, key: str, **kwargs) -> str:
        parts = key.split(".")
        node = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return key
        if not isinstance(node, str):
            return key
        return node.format(**kwargs) if kwargs else node


# Singleton default
_i18n = I18n("en")


def set_language(lang: str):
    _i18n.load(lang)


def get_language() -> str:
    return _i18n._lang


def t(key: str, default: str = "", **kwargs) -> str:
    val = _i18n.t(key, **kwargs)
    if val == key and default:
        return default
    return val
