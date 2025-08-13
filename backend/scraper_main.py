import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import time

# ensure local imports (db.py) work when running this file directly
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv

import db  # now safe

from supabase import create_client

from providers.globeair import GlobeAirProvider
from common.types import FlightRecord
from common.airports import build_indexes



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JetCheck scraper orchestrator")
    p.add_argument(
        "--provider",
        choices=["all", "globeair"],
        default=os.getenv("SCRAPER_PROVIDER", "all"),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch & parse, but do not write to DB",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Verbose debug logging (also honors SCRAPER_DEBUG=1)",
    )
    p.add_argument(
        "--debug-dir",
        default=os.getenv("SCRAPER_DEBUG_DIR"),
        help="Directory to write debug artifacts (defaults to /tmp/jetcheck if --debug is set)",
    )
    return p.parse_args()


# helper:
def run_provider(name: str, debug: bool, debug_dir: str | None) -> list[FlightRecord]:
    if name == "globeair":
        return GlobeAirProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    raise ValueError(f"Unknown provider: {name}")


# Helper to refresh flight statuses via Supabase RPC
def refresh_statuses() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("⚠️  Skipping status refresh: missing SUPABASE_URL or key", file=sys.stderr)
        return
    try:
        sb = create_client(url, key)
        sb.rpc("refresh_flight_statuses_run").execute()
        print("🧹 Flight statuses refreshed (refresh_flight_statuses).")
    except Exception as e:
        print(f"⚠️  Status refresh failed: {e}", file=sys.stderr)


def main():
    load_dotenv()

    args = parse_args()
    env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
    debug = args.debug or env_debug
    debug_dir = args.debug_dir or ("/tmp/jetcheck" if debug else None)

    # Preload airport indexes once (fail fast if airports table missing)
    try:
        build_indexes()
        if debug:
            print("🗺️  Airports index preloaded.")
    except Exception as e:
        # Still proceed; providers lazily resolve but this helps catch config issues early
        print(f"⚠️  Could not preload airports index: {e}", file=sys.stderr)

    print("🔄 Starte Scraper…")
    t_start = time.time()

    providers = (
        ["globeair"] if args.provider == "all" else [args.provider]
    )
    durations: dict[str, float] = {}

    parsed_status_counts: Counter[str] = Counter()
    saved_status_counts: Counter[str] = Counter()
    save_errors: list[str] = []

    total_records: list[FlightRecord] = []
    provider_counts: dict[str, int] = {}
    for prov in providers:
        try:
            p0 = time.time()
            recs = run_provider(prov, debug=debug, debug_dir=debug_dir)
            print(f"ℹ️  {prov.capitalize()}: {len(recs)}")
            provider_counts[prov] = len(recs)
            total_records.extend(recs)
            for r in recs:
                st = str((r.get("status") or "")).lower() or "unknown"
                parsed_status_counts[st] += 1
            durations[prov] = time.time() - p0
        except Exception as e:
            print(f"❌ {prov} fetch error: {e}", file=sys.stderr)
            durations[prov] = time.time() - p0

    print(f"ℹ️  Insgesamt {len(total_records)} Datensätze geparst.")

    # Write a parse-only debug report (also on dry-run)
    if debug and debug_dir:
        try:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            report_path = Path(debug_dir) / "scrape_report.txt"
            lines = [
                f"JetCheck scrape report — {datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')}",
                "",
                "Per-provider counts:",
            ]
            for k in ["globeair"]:
                if k in provider_counts:
                    dur = durations.get(k, 0.0)
                    lines.append(f"  - {k}: {provider_counts[k]} (in {dur:.2f}s)")

            total_dur = time.time() - t_start
            lines += [
                "",
                f"Parsed total: {len(total_records)}",
                "Parsed by status:",
            ]
            # stable order for readability
            for st in ["available", "pending", "unavailable", "unknown"]:
                c = parsed_status_counts.get(st, 0)
                if c:
                    lines.append(f"  - {st}: {c}")
            if not any(parsed_status_counts.values()):
                lines.append("  - (no status parsed)")

            lines += [
                "",
                f"Elapsed (so far): {total_dur:.2f}s",
            ]
            if args.dry_run:
                lines.append("(This report was generated before DB writes — dry run)")
        except Exception as e:
            print(f"⚠️  Failed to write debug report: {e}", file=sys.stderr)

    if args.dry_run:
        print("💡 Dry-run: keine Writes in die DB.")
        return

    saved = 0
    for r in total_records:
        try:
            db.upsert_flight_and_snapshot(r)
            saved += 1
            st = str((r.get("status") or "")).lower() or "unknown"
            saved_status_counts[st] += 1
        except Exception as e:
            oc = r.get("origin_iata")
            dc = r.get("destination_iata")
            msg = f"{oc or '??'}→{dc or '??'} — {e}"
            save_errors.append(msg)
            print(f"❌ Fehler für {oc}→{dc}: {e}", file=sys.stderr)

    # Combined debug report
    if debug and debug_dir:
        try:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            report_path = Path(debug_dir) / "scrape_report.txt"
            lines = [
                f"JetCheck scrape report — {datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')}",
                "",
                "Per-provider counts:",
            ]
            for k in ["globeair"]:
                if k in provider_counts:
                    dur = durations.get(k, 0.0)
                    lines.append(f"  - {k}: {provider_counts[k]} (in {dur:.2f}s)")

            total_dur = time.time() - t_start
            saved_snapshots = saved  # one snapshot per successful upsert

            lines += [
                "",
                f"Parsed total: {len(total_records)}",
                "Parsed by status:",
            ]
            for st in ["available", "pending", "unavailable", "unknown"]:
                c = parsed_status_counts.get(st, 0)
                if c:
                    lines.append(f"  - {st}: {c}")
            if not any(parsed_status_counts.values()):
                lines.append("  - (no status parsed)")

            lines += [
                "",
                f"Flights saved: {saved}",
                f"Snapshots taken: {saved_snapshots}",
                "Saved by status:",
            ]
            for st in ["available", "pending", "unavailable", "unknown"]:
                c = saved_status_counts.get(st, 0)
                if c:
                    lines.append(f"  - {st}: {c}")
            if not any(saved_status_counts.values()):
                lines.append("  - (no flights saved)")

            if save_errors:
                lines += [
                    "",
                    f"Save errors: {len(save_errors)}",
                ]
                # list max 10 to keep report compact
                for err in save_errors[:10]:
                    lines.append(f"  - {err}")
                if len(save_errors) > 10:
                    lines.append(f"  ... and {len(save_errors)-10} more")

            lines += [
                "",
                f"Elapsed: {total_dur:.2f}s",
            ]
        except Exception as e:
            print(f"⚠️  Failed to write debug report: {e}", file=sys.stderr)

    refresh_statuses()
    print(f"✅ Saved flights: {saved} — snapshots: {saved} — statuses: {dict(saved_status_counts)}")


if __name__ == "__main__":
    main()