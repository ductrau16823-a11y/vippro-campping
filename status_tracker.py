"""
StatusTracker: Ghi trang thai realtime vao status.json de dashboard doc.
Phien ban cho campaign automation.
"""

import json
from datetime import datetime

from camp_selectors import STATUS_FILE


class StatusTracker:

    def __init__(self, status_file=STATUS_FILE):
        self.file = status_file
        self.data = {
            "started_at": datetime.now().isoformat(),
            "updated_at": None,
            "status": "running",
            "total_accounts": 0,
            "processed_accounts": 0,
            "total_campaigns_created": 0,
            "current_account": None,
            "current_step": None,
            "results": [],
            "logs": [],
        }
        self._save()

    def log(self, message, level="info"):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
        self.data["logs"].append(entry)
        if len(self.data["logs"]) > 200:
            self.data["logs"] = self.data["logs"][-200:]

        icon = {"info": " ", "success": "+", "error": "!", "warn": "?"}
        prefix = icon.get(level, " ")
        print(f"  [{prefix}] {message}")
        self._save()

    def set_current(self, account=None, step=None):
        if account:
            self.data["current_account"] = account
        if step:
            self.data["current_step"] = step
        self._save()

    def add_account_result(self, account_id, gmail, campaigns_created, status, error=None):
        self.data["results"].append({
            "account_id": account_id,
            "gmail": gmail,
            "campaigns_created": campaigns_created,
            "status": status,
            "error": error,
            "completed_at": datetime.now().isoformat(),
        })
        self.data["processed_accounts"] += 1
        self.data["total_campaigns_created"] += campaigns_created
        self._save()

    def finish(self, status="completed"):
        self.data["status"] = status
        self.data["current_account"] = None
        self.data["current_step"] = "Hoan thanh"
        self._save()

    def _save(self):
        self.data["updated_at"] = datetime.now().isoformat()
        try:
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
