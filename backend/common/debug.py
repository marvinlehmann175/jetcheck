# backend/common/debug.py
from __future__ import annotations
from pathlib import Path
from typing import List, Optional

class DebugCollector:
    """
    Tiny helper to dump HTML and a plain-text report for a given provider.
    No imports from providers here (avoid circular imports).
    """
    def __init__(self, provider_name: str, enabled: bool, outdir: Optional[str] = None):
        self.provider = provider_name
        self.enabled = bool(enabled)
        self.outdir = Path(outdir) if (enabled and outdir) else None
        self.lines: List[str] = []
        if self.outdir:
            self.outdir.mkdir(parents=True, exist_ok=True)

    def add(self, line: str) -> None:
        if self.enabled:
            self.lines.append(f"[{self.provider}] {line}")

    def save_html(self, filename: str, html: str) -> None:
        if not (self.enabled and self.outdir):
            return
        path = self.outdir / filename
        path.write_text(html, encoding="utf-8")
        print(f"🪵 DEBUG saved: {path}")

    def write_report(self, filename: str = "report.txt") -> None:
        if not (self.enabled and self.outdir):
            return
        (self.outdir / filename).write_text("\n".join(self.lines) + "\n", encoding="utf-8")