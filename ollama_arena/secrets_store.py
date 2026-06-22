"""Encrypted local storage for user-entered provider API keys.

Keys are encrypted at rest with a locally-generated Fernet key (its own
0600 file), and the encrypted store file is itself 0600 -- this protects
against another user/process on the same machine casually reading the
file, and the value never appears in any API response or log line.

This does NOT protect against an attacker with full read access to this
user's account -- no local secret store can, short of hardware-backed
storage (a Secure Enclave / TPM-backed OS keychain). That's the honest
limit of "encrypted file on disk," not a gap specific to this module.

Env vars (OPENROUTER_API_KEY etc.) remain the primary, documented path
and always take priority when set -- see openai_compat.py's
OpenAICompatBackend.__init__. This store is a convenience layer for
users who'd rather paste a key into the Providers tab than touch a
shell, not a replacement for env-based config.
"""
from __future__ import annotations

import json
import os
import stat

_DEFAULT_DIR = os.path.expanduser("~/.config/ollama-arena")
_DEFAULT_KEY_PATH = os.path.join(_DEFAULT_DIR, "secret.key")
_DEFAULT_STORE_PATH = os.path.join(_DEFAULT_DIR, "api_keys.enc.json")


class SecretsUnavailable(RuntimeError):
    """Raised when the `cryptography` package isn't installed."""


def _restrict(path: str) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 -- owner read/write only
    except OSError:
        pass


def _get_fernet(key_path: str):
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise SecretsUnavailable(
            "Storing API keys requires the 'cryptography' package: "
            "pip install 'ollama-arena[web]'"
        ) from e
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        fd = os.open(key_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    _restrict(key_path)
    return Fernet(key)


class SecretsStore:
    """One store per (key_path, store_path) pair. Tests inject tmp paths;
    web.py's run_web() threads its own paths through the same way it
    already does for role_models.json, so tests never touch the real
    ~/.config/ollama-arena."""

    def __init__(self, key_path: str | None = None, store_path: str | None = None):
        self._key_path = key_path or _DEFAULT_KEY_PATH
        self._store_path = store_path or _DEFAULT_STORE_PATH

    def _load_raw(self) -> dict:
        if not os.path.exists(self._store_path):
            return {}
        try:
            with open(self._store_path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_raw(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
        fd = os.open(self._store_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
        _restrict(self._store_path)

    def set_key(self, provider: str, value: str) -> None:
        fernet = _get_fernet(self._key_path)
        data = self._load_raw()
        data[provider] = fernet.encrypt(value.encode()).decode()
        self._save_raw(data)

    def get_key(self, provider: str) -> str | None:
        token = self._load_raw().get(provider)
        if not token:
            return None
        try:
            fernet = _get_fernet(self._key_path)
            return fernet.decrypt(token.encode()).decode()
        except Exception:
            return None

    def has_key(self, provider: str) -> bool:
        return provider in self._load_raw()

    def clear_key(self, provider: str) -> None:
        data = self._load_raw()
        if provider in data:
            del data[provider]
            self._save_raw(data)

    def configured_providers(self) -> set[str]:
        return set(self._load_raw().keys())


_default_store: SecretsStore | None = None


def _store() -> SecretsStore:
    global _default_store
    if _default_store is None:
        _default_store = SecretsStore()
    return _default_store


def set_key(provider: str, value: str) -> None:
    _store().set_key(provider, value)


def get_key(provider: str) -> str | None:
    try:
        return _store().get_key(provider)
    except SecretsUnavailable:
        return None


def has_key(provider: str) -> bool:
    return _store().has_key(provider)


def clear_key(provider: str) -> None:
    _store().clear_key(provider)


def configured_providers() -> set[str]:
    return _store().configured_providers()
