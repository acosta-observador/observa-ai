"""Cliente HTTP educado: User-Agent identificado, rate limit por host e cache em disco."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from ..config import settings


class PoliteClient:
    def __init__(self, min_interval: float = 1.0, cache_ttl: int = 3600, timeout: float = 30.0):
        self.min_interval = min_interval
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._last: Dict[str, float] = {}

    def _cache_path(self, url: str) -> Path:
        d = Path(settings.cache_dir)
        d.mkdir(parents=True, exist_ok=True)
        return d / hashlib.sha1(url.encode()).hexdigest()

    def get_text(self, url: str, headers: Optional[Dict[str, str]] = None, use_cache: bool = True) -> str:
        p = self._cache_path(url)
        if use_cache and self.cache_ttl and p.exists() and time.time() - p.stat().st_mtime < self.cache_ttl:
            return p.read_text(encoding="utf-8")
        host = urlparse(url).netloc
        wait = self.min_interval - (time.time() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        h = {"User-Agent": settings.user_agent}
        h.update(headers or {})
        r = httpx.get(url, headers=h, timeout=self.timeout, follow_redirects=True)
        self._last[host] = time.time()
        r.raise_for_status()
        if use_cache and self.cache_ttl:
            try:
                p.write_text(r.text, encoding="utf-8")
            except OSError:
                pass
        return r.text

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None, use_cache: bool = True) -> Any:
        return json.loads(self.get_text(url, headers=headers, use_cache=use_cache))
