import os
import sys
import argparse

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
    return p.parse_args()


# helper:
def run_provider(name: str):
    if name == "globeair":
        return GlobeAirProvider().fetch_all()
    if name == "asl":
        return ASLProvider().fetch_all()
    if name == "eaviation":
        return EaviationProvider().fetch_all()
    if name == "all":
        # handled by loop
        raise ValueError("use loop")
    raise ValueError(f"Unknown provider: {name}")


def main():
    load_dotenv()

    args = parse_args()
    env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
    debug = args.debug or env_debug

    # Preload airport indexes once (fail fast if airports table missing)
    try:
        build_indexes()
        if debug:
            print("🗺️  Airports index preloaded.")
    except Exception as e:
        # Still proceed; providers lazily resolve but this helps catch config issues early
        print(f"⚠️  Could not preload airports index: {e}", file=sys.stderr)

    print("🔄 Starte Scraper…")

    providers = (
        ["globeair", "asl", "eaviation"] if args.provider == "all" else [args.provider]
    )

    total_records: list[FlightRecord] = []
    for prov in providers:
        try:
            recs = run_provider(prov)
            print(f"ℹ️  {prov.capitalize()}: {len(recs)}")
            total_records.extend(recs)
        except Exception as e:
            print(f"❌ {prov} fetch error: {e}", file=sys.stderr)

    print(f"ℹ️  Insgesamt {len(total_records)} Datensätze geparst.")

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

    print(f"✅ {saved} Flüge/Snapshots gespeichert.")


if __name__ == "__main__":
    main()