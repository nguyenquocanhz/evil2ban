# -*- coding: utf-8 -*-
"""Giai quyet duong dan he thong (co the override bang env)."""
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent.parent
STATIC_DIR = PKG_DIR / "static"


def state_dir() -> Path:
    env = os.environ.get("E2B_STATE_DIR")
    if env:
        return Path(env)
    if Path("/var/lib/evil2ban").exists():
        return Path("/var/lib/evil2ban")
    return REPO_ROOT


def db_path() -> Path:
    env = os.environ.get("E2B_DB")
    if env:
        return Path(env)
    return state_dir() / "evil2ban.db"
