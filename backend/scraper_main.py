import os
import sys
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

# ensure local imports (db.py) work when running this file directly
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv
from supabase import create_client

# keep db import if you use other helpers there
import db
from db import SYSTEM_USER_ID

from providers.globeair import GlobeAirProvider
from common.types import FlightRecord
from common.airports import build_indexes, get_latlon
from common.canonical import canonical_hash


# ---------- helpers ----------
def now_utc_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


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
        help="Directory to write debug artifacts (defaults to /tmp/jetcheck)",
    )
    return p.parse_args()


def run_provider(name: str, debug: bool, debug_dir: str | None) -> list[FlightRecord]:
    if name == "globeair":
        return GlobeAirProvider(debug=debug, debug_dir=debug_dir).fetch_all()
    raise ValueError(f"Unknown provider: {name}")


def upsert_canonical(sb, record, price_eur, c_hash, provider_ref):
    o = (record.get("origin_iata") or "").upper()
    d = (record.get("destination_iata") or "").upper()
    olat, olon = get_latlon(o)
    dlat, dlon = get_latlon(d)

    existing = (
        sb.table("flights")
          .select("*")
          .eq("canonical_hash", c_hash)
          .limit(1)
          .execute()
          .data
    )

    if existing:
        row = existing[0]
        refs = row.get("provider_refs") or []
        sig = {(r.get("provider"), r.get("id")) for r in refs}
        if (provider_ref["provider"], provider_ref.get("id")) not in sig:
            refs.append(provider_ref)

        prices = [r.get("price_eur") for r in refs if isinstance(r.get("price_eur"), (int, float))]
        best_price = min(prices) if prices else None

        link = None
        if best_price is not None:
            for r in refs:
                if r.get("price_eur") == best_price and r.get("link"):
                    link = r["link"]; break
        if link is None and refs:
            refs_sorted = sorted(refs, key=lambda r: r.get("seen_at", ""), reverse=True)
            link = refs_sorted[0].get("link")

        statuses = [str((r.get("status") or "")).lower() for r in refs]
        if "available" in statuses:
            status_latest = "available"
        elif "pending" in statuses:
            status_latest = "pending"
        else:
            status_latest = row.get("status_latest") or (record.get("status") or "")

        update_payload = {
            "provider_refs": refs,
            "price_eur": best_price,
            "link_latest": link,
            "status_latest": status_latest,
            "last_seen_at": now_utc_iso(),
            "origin_lat": row.get("origin_lat") or olat,
            "origin_lon": row.get("origin_lon") or olon,
            "destination_lat": row.get("destination_lat") or dlat,
            "destination_lon": row.get("destination_lon") or dlon,
        }
        # ✅ backfill required fields if missing
        if not row.get("user_id"):
            update_payload["user_id"] = SYSTEM_USER_ID
        if not row.get("source"):
            # for canonical rows with multiple providers, pick the latest provider;
            # “canonical” also works if you prefer a neutral label.
            update_payload["source"] = provider_ref.get("provider") or (record.get("source") or "canonical")

        sb.table("flights").update(update_payload).eq("id", row["id"]).execute()

    else:
        payload = {
            "user_id": SYSTEM_USER_ID,  # NOT NULL
            # keep a non-empty source; either latest provider or a neutral label
            "source": provider_ref.get("provider") or (record.get("source") or "canonical"),
            "canonical_hash": c_hash,   # your new canonical hash (keep storing it)
            "origin_iata": o,
            "origin_name": record.get("origin_name") or o,
            "destination_iata": d,
            "destination_name": record.get("destination_name") or d,
            "departure_ts": record.get("departure_ts"),
            "arrival_ts": record.get("arrival_ts"),
            "aircraft": record.get("aircraft"),
            "provider_refs": [provider_ref],
            "price_eur": price_eur,
            "currency_effective": "EUR",
            "status_latest": (record.get("status_latest") or record.get("status") or ""),
            "last_seen_at": now_utc_iso(),
            "link_latest": record.get("link_latest") or record.get("link"),
            "origin_lat": olat, "origin_lon": olon,
            "destination_lat": dlat, "destination_lon": dlon,
        }

        # ⭐ important: upsert on the legacy unique key so duplicates update instead of erroring
        sb.table("flights").upsert(
            payload,
            on_conflict="hash"   # uses the existing unique index flights_hash_uidx
        ).execute()

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


# ---------- main ----------
def main():
    load_dotenv()

    SYSTEM_USER_ID = os.getenv("SYSTEM_USER_ID")
    if not SYSTEM_USER_ID:
        print("❌ Missing SYSTEM_USER_ID (auth.users.id UUID)", file=sys.stderr)
        sys.exit(1)

    # Warm the airport cache once (get_latlon will use it)
    build_indexes()

    args = parse_args()
    env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
    debug = args.debug or env_debug

    # Supabase client (once)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("❌ Missing SUPABASE_URL or key", file=sys.stderr)
        sys.exit(1)
    sb = create_client(url, key)

    # Report directory
    report_dir = args.debug_dir or "/tmp/jetcheck"
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    report_path = Path(report_dir) / "scrape_report.txt"

    print("🔄 Starte Scraper…")
    t_start = time.time()

    # choose providers
    all_providers = ["globeair"]
    providers = all_providers if args.provider == "all" else [args.provider]

    durations: dict[str, float] = {}
    parsed_status_counts: Counter[str] = Counter()
    saved_status_counts: Counter[str] = Counter()
    save_errors: list[str] = []
    total_records: list[FlightRecord] = []
    provider_counts: dict[str, int] = {}

    # fetch
    for prov in providers:
        try:
            p0 = time.time()
            recs = run_provider(prov, debug=debug, debug_dir=report_dir if debug else None)
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

    # write (unless dry-run)
    if args.dry_run:
        print("💡 Dry-run: keine Writes in die DB.")
    else:
        saved = 0
        for r in total_records:
            try:
                # canonical hash
                c_hash = canonical_hash(
                    r.get("origin_iata"),
                    r.get("destination_iata"),
                    r.get("departure_ts"),
                    r.get("aircraft"),
                )

                # normalize price to EUR (stub; extend with FX later)
                price_eur = None
                if isinstance(r.get("price_current"), (int, float)):
                    if (r.get("currency_effective") or "EUR").upper() == "EUR":
                        price_eur = float(r["price_current"])
                    else:
                        price_eur = None  # TODO: convert

                provider_ref = {
                    "provider": r.get("source") or "unknown",
                    "id": r.get("id"),
                    "link": r.get("link_latest") or r.get("link"),
                    "price_eur": price_eur,
                    "currency": r.get("currency_effective") or "EUR",
                    "status": r.get("status_latest") or r.get("status"),
                    "seen_at": now_utc_iso(),
                }

                upsert_canonical(sb, r, price_eur, c_hash, provider_ref)

                saved += 1
                st = str((r.get("status") or "")).lower() or "unknown"
                saved_status_counts[st] += 1

            except Exception as e:
                oc = r.get("origin_iata")
                dc = r.get("destination_iata")
                msg = f"{oc or '??'}→{dc or '??'} — {e}"
                save_errors.append(msg)
                print(f"❌ Fehler für {oc}→{dc}: {e}", file=sys.stderr)

    # ---- ALWAYS write a final scrape report (for monitoring) ----
    try:
        total_dur = time.time() - t_start
        saved_total = 0 if args.dry_run else sum(saved_status_counts.values())
        statuses = Counter([(r.get("status") or "pending").lower() for r in total_records])

        lines = [
            f"JetCheck scrape report — {datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')}",
            "",
            "Per-provider counts:",
        ]
        for k in providers:
            v = provider_counts.get(k, 0)
            lines.append(f"  - {k}: {v} (in {durations.get(k, 0.0):.2f}s)")

        lines += [
            "",
            f"Total parsed: {len(total_records)}",
            f"Total saved: {saved_total}",
            f"Elapsed: {total_dur:.2f}s",
            f"Statuses: {dict(statuses)}",
        ]

        if save_errors and not args.dry_run:
            lines += ["", f"Save errors: {len(save_errors)}"]
            for err in save_errors[:10]:
                lines.append(f"  - {err}")
            if len(save_errors) > 10:
                lines.append(f"  ... and {len(save_errors)-10} more")

        summary = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "providers": provider_counts,
            "total_parsed": len(total_records),
            "total_saved": saved_total,
            "durations_sec": durations,
            "statuses": dict(statuses),
            "dry_run": args.dry_run,
        }
        lines += ["", "JETCHECK_SUMMARY " + json.dumps(summary, separators=(",", ":"))]

        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"🧾 Debug report written: {report_path}")
    except Exception as e:
        print(f"⚠️  Failed to write final debug report: {e}", file=sys.stderr)

    # Refresh statuses unless dry-run
    if not args.dry_run:
        refresh_statuses()
        print(f"✅ Saved flights: {sum(saved_status_counts.values())} — snapshots: {sum(saved_status_counts.values())} — statuses: {dict(saved_status_counts)}")


if __name__ == "__main__":
    main()