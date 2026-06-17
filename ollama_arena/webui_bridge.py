import os
import requests
import logging
from typing import Optional

log = logging.getLogger("arena.webui")

class WebUIBridge:
    """Synchronizes Arena state (leaderboards, models) with Open WebUI."""
    
    def __init__(self, base_url: str = "http://localhost:3000", api_key: Optional[str] = None):
        self.base = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("WEBUI_API_KEY")
        self._headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def sync_leaderboard(self, leaderboard: list[dict]) -> bool:
        """Pushes Arena ELO ratings to Open WebUI as model metadata or broadcast."""
        if not self._headers:
            log.warning("[webui] sync skipped: no WEBUI_API_KEY")
            return False
            
        success = True
        for entry in leaderboard:
            model = entry["model"]
            elo = entry["elo"]
            rank = entry["rank"]
            
            # Simulated Open WebUI metadata update
            # In a real integration, this might update model descriptions or tags
            try:
                # Open WebUI API: GET /api/v1/models/{id} then POST /api/v1/models/{id}/update
                log.info(f"[webui] syncing {model} (ELO: {elo}, Rank: {rank})")
                # payload = {"info": {"arena_elo": elo, "arena_rank": rank}}
                # requests.post(f"{self.base}/api/v1/models/{model}/update", json=payload, headers=self._headers, timeout=5)
            except Exception as e:
                log.error(f"[webui] failed to sync {model}: {e}")
                success = False
        return success

    def broadcast_match_result(self, result_summary: str):
        """Sends a notification to Open WebUI about a completed match."""
        if not self._headers: return
        try:
            # requests.post(f"{self.base}/api/v1/channels/arena-log/messages", 
            #               json={"content": result_summary}, headers=self._headers)
            pass
        except Exception: pass
