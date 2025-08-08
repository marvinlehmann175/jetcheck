import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
import time

# ensure local imports (db.py) work when running this file directly
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv

import db  # now safe

from providers.globeair import GlobeAirProvider
from providers.asl import ASLProvider
from providers.eaviation import EaviationProvider
from common.types import FlightRecord
from common.airports import build_indexes



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JetCheck scraper orchestrator")
    p.add_argument(
        "--provider",
        choices=["all", "globeair", "asl", "eaviation"],
        default=os.getenv("SCRAPER_PROVIDER", "all"),
        help="Which provider to run (default: all)",
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
def run_provider(name: str, *, debug: bool, debug_dir: str | None):
    if name == "globeair":
        return GlobeAirProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "asl":
        return ASLProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "eaviation":
        return EaviationProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "all":
        # handled by loop
        raise ValueError("use loop")
    raise ValueError(f"Unknown provider: {name}")


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
        ["globeair", "asl", "eaviation"] if args.provider == "all" else [args.provider]
    )
    durations: dict[str, float] = {}

    total_records: list[FlightRecord] = []
    provider_counts: dict[str, int] = {}
    for prov in providers:
        try:
            p0 = time.time()
            recs = run_provider(prov, debug=debug, debug_dir=debug_dir)
            print(f"ℹ️  {prov.capitalize()}: {len(recs)}")
            provider_counts[prov] = len(recs)
            total_records.extend(recs)
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
                f"JetCheck scrape report — {datetime.utcnow().isoformat(timespec='seconds')}Z",
                "",
                "Per-provider counts:",
            ]
            for k in ["globeair", "asl", "eaviation"]:
                if k in provider_counts:
                    dur = durations.get(k, 0.0)
                    lines.append(f"  - {k}: {provider_counts[k]} (in {dur:.2f}s)")
            total_dur = time.time() - t_start
            lines += [
                "",
                f"Total parsed: {len(total_records)}",
                f"Elapsed: {total_dur:.2f}s",
                "(This report was generated before DB writes.)" if args.dry_run else "",
            ]
            report_path.write_text("\n".join([s for s in lines if s != ""]), encoding="utf-8")
            print(f"🧾 Debug report written: {report_path}")
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
        except Exception as e:
            oc = r.get("origin_iata")
            dc = r.get("destination_iata")
            print(f"❌ Fehler für {oc}→{dc}: {e}", file=sys.stderr)

    # Combined debug report
    if debug and debug_dir:
        try:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            report_path = Path(debug_dir) / "scrape_report.txt"
            lines = [
                f"JetCheck scrape report — {datetime.utcnow().isoformat(timespec='seconds')}Z",
                "",
                "Per-provider counts:",
            ]
            for k in ["globeair", "asl", "eaviation"]:
                if k in provider_counts:
                    dur = durations.get(k, 0.0)
                    lines.append(f"  - {k}: {provider_counts[k]} (in {dur:.2f}s)")
            total_dur = time.time() - t_start
            lines += [
                "",
                f"Total parsed: {len(total_records)}",
                f"Total saved: {saved}",
                f"Elapsed: {total_dur:.2f}s",
            ]
            report_path.write_text("\n".join(lines), encoding="utf-8")
            print(f"🧾 Debug report written: {report_path}")
        except Exception as e:
            print(f"⚠️  Failed to write debug report: {e}", file=sys.stderr)

    print(f"✅ {saved} Flüge/Snapshots gespeichert.")


if __name__ == "__main__":
    main()