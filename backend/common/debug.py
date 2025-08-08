# backend/common/debug.py
from __future__ import annotations
import os, json, time, datetime as dt
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

@dataclass
class DebugEvent:
    t: str
    level: str
    msg: str
    extra: Dict[str, Any]

class DebugCollector:
    """
    Lightweight debug collector that can:
    - log() arbitrary events
    - save_text() artifacts (HTML, JSON, etc.)
    - record selector counts & timings
    - export a compact JSON report at the end
    """
    def __init__(self, provider: str, enabled: bool, outdir: Optional[str] = None):
        self.provider = provider
        self.enabled = enabled
        self.outdir = outdir or "/tmp/jetcheck"
        self.events: List[DebugEvent] = []
        self.artifacts: List[str] = []  # file paths

        if self.enabled:
            os.makedirs(self.outdir, exist_ok=True)

    def log(self, msg: str, level: str = "INFO", **extra: Any):
        if not self.enabled:
            return
        ev = DebugEvent(t=_now_iso(), level=level, msg=msg, extra=extra or {})
        self.events.append(ev)
        # mirror to stdout for quick visibility
        print(f"[{self.provider}] {level}: {msg}" + (f" | {extra}" if extra else ""))

    def save_text(self, name: str, text: str):
        if not self.enabled:
            return None
        path = os.path.join(self.outdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.artifacts.append(path)
        print(f"🪵 DEBUG saved: {path}")
        return path

    def count(self, label: str, **selector_counts: int):
        """Record counts for CSS selectors or any metric."""
        self.log(f"counts: {label}", **selector_counts)

    def timeit(self, label: str):
        """Context manager to time arbitrary blocks."""
        class _Timer:
            def __init__(self, outer: DebugCollector, label: str):
                self.outer = outer
                self.label = label
            def __enter__(self):
                self.t0 = time.perf_counter()
            def __exit__(self, *exc):
                dt_s = (time.perf_counter() - self.t0) * 1000.0
                self.outer.log(f"timing: {self.label}", ms=round(dt_s, 1))
        return _Timer(self, label)

    def to_json(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "outdir": self.outdir,
            "events": [asdict(e) for e in self.events],
            "artifacts": self.artifacts,
        }