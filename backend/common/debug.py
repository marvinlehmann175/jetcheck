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

    def log(self, key: str, value=None) -> None:
        """
        Log a message. If `value` is provided, store it as a key/value pair.
        Supports existing calls like `dbg.log("message")` and new calls like
        `dbg.log("items_ssr", 12)`.
        """
        if value is not None:
            self.add_kv(key, value)
        else:
            self.add(key)

    def add_kv(self, key: str, value) -> None:
        """Convenience helper to log key/value pairs in a consistent way."""
        self.add(f"{key} = {value}")

    def save_text(self, filename: str, text: str) -> None:
        """Write arbitrary text (HTML or plain) to a debug file in outdir."""
        if not (self.enabled and self.outdir):
            return
        path = self.outdir / filename
        path.write_text(text, encoding="utf-8")
        print(f"🪵 DEBUG saved: {path}")

    def save(self, filename: str, text: str) -> None:
        """Backwards-compatible alias for save_text()."""
        self.save_text(filename, text)

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