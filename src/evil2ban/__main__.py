# -*- coding: utf-8 -*-
"""python -m evil2ban / evil2ban-server — chay backend (host/port tu SQLite)."""
import uvicorn

from .paths import db_path
from .data.database import Database
from .data.repositories import SettingsRepository


def main():
    s = SettingsRepository(Database(db_path()))
    s.seed_defaults()
    host = s.get("server.host", "E2B_HOST", "127.0.0.1")
    port = s.get_int("server.port", "E2B_PORT", 8793)
    uvicorn.run("evil2ban.web.app:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
