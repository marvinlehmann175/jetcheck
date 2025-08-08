import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

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
        help="Directory to dump provider HTML and a combined scrape_report.txt",
    )
    return p.parse_args()


def run_provider(name: str, *, debug: bool, debug_dir: str | None):
    if name == "globeair":
        return GlobeAirProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "asl":
        return ASLProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "eaviation":
        return EaviationProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    if name == "all":
        raise ValueError("use loop")
    raise ValueError(f"Unknown provider: {name}")


def main():
    load_dotenv()

    args = parse_args()
    env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
    debug = bool(args.debug or env_debug)
    debug_dir = args.debug_dir

    # Prepare combined report
    report_lines: list[str] = []
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if debug_dir:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        report_lines.append(f"# JetCheck scrape report\n")
        report_lines.append(f"- Timestamp: {ts}")
        report_lines.append(f"- Debug dir: {Path(debug_dir).resolve()}")
        report_lines.append("")

    # Preload airport indexes once (fail fast if airports table missing)
    try:
        build_indexes()
        if debug:
            print("🗺️  Airports index preloaded.")
        if debug_dir:
            report_lines.append("✅ Airports index preloaded.")
    except Exception as e:
        msg = f"⚠️  Could not preload airports index: {e}"
        print(msg, file=sys.stderr)
        if debug_dir:
            report_lines.append(msg)

    print("🔄 Starte Scraper…")

    providers = (
        ["globeair", "asl", "eaviation"] if args.provider == "all" else [args.provider]
    )

    total_records: list[FlightRecord] = []
    per_provider_counts: dict[str, int] = {}

    for prov in providers:
        try:
            recs = run_provider(prov, debug=debug, debug_dir=debug_dir)
            per_provider_counts[prov] = len(recs)
            print(f"ℹ️  {prov.capitalize()}: {len(recs)}")
            if debug_dir:
                report_lines.append(f"- {prov}: {len(recs)} records")
            total_records.extend(recs)
        except Exception as e:
            err = f"❌ {prov} fetch error: {e}"
            print(err, file=sys.stderr)
            if debug_dir:
                report_lines.append(err)

    print(f"ℹ️  Insgesamt {len(total_records)} Datensätze geparst.")
    if debug_dir:
        report_lines.append(f"\n**Total:** {len(total_records)}")

    if args.dry_run:
        print("💡 Dry-run: keine Writes in die DB.")
        if debug_dir:
            report_lines.append("\nDry-run: no DB writes.")
        # write combined report
        if debug_dir:
            (Path(debug_dir) / "scrape_report.txt").write_text(
                "\n".join(report_lines) + "\n", encoding="utf-8"
            )
        return

    saved = 0
    for r in total_records:
        try:
            db.upsert_flight_and_snapshot(r)
            saved += 1
        except Exception as e:
            oc = r.get("origin_iata")
            dc = r.get("destination_iata")
            err = f"❌ Fehler für {oc}→{dc}: {e}"
            print(err, file=sys.stderr)
            if debug_dir:
                report_lines.append(err)

    print(f"✅ {saved} Flüge/Snapshots gespeichert.")
    if debug_dir:
        report_lines.append(f"\nSaved: {saved} flight snapshots.")
        (Path(debug_dir) / "scrape_report.txt").write_text(
            "\n".join(report_lines) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()