# -*- coding: utf-8 -*-
"""Notifier qua script san co /usr/local/bin/f2b-notify.sh (Telegram/Slack/Discord)."""
import os
import subprocess

from ..core.interfaces import Notifier


class ScriptNotifier(Notifier):
    def __init__(self, script):
        self.script = script

    def send(self, event, jail, ip, failures="") -> bool:
        if not self.script or not os.path.exists(self.script):
            return False
        try:
            subprocess.Popen(
                [self.script, str(event), str(jail), str(ip), str(failures)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:  # noqa: BLE001
            return False


class NullNotifier(Notifier):
    def send(self, event, jail, ip, failures="") -> bool:
        return False
