import os
import sys
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from common.airports import build_indexes

# ensure local imports (db.py) work when running this file directly
sys.path.append(os.path.dirname(__file__))

from dotenv import load_dotenv

# Reuse the shared Supabase client + validated env from db.py
import db
from db import get_supabase, SYSTEM_USER_ID

from providers.globeair import GlobeAirProvider
from common.types import FlightRecord
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


def upsert_canonical(sb, record, price_eur, c_hash, provider_ref, system_user_id):
    """
    Insert/update the canonical flight row identified by canonical_hash.
    - Only writes stable fields (identity + static metadata).
    - Never writes live/derived fields (status, status_latest, price_eur, link_latest, last_seen_at).
    - Merges provider_refs without duplicates (by provider + provider id or link).
    """
    o = (record.get("origin_iata") or "").upper()
    d = (record.get("destination_iata") or "").upper()

    # Fetch the one canonical row (if any)
    existing = (
        sb.table("flights")
          .select("id, user_id, source, provider_refs")
          .eq("canonical_hash", c_hash)
          .limit(1)
          .execute()
          .data
    )

    if existing:
        row = existing[0]

        # Merge provider_refs without dupes
        refs = row.get("provider_refs") or []
        sig = {(r.get("provider"), r.get("id") or r.get("link")) for r in refs}
        k = (provider_ref.get("provider"), provider_ref.get("id") or provider_ref.get("link"))
        if k not in sig:
            refs.append(provider_ref)

        update_payload = {
            "provider_refs": refs,
        }

        # Backfill static fields if missing
        if not row.get("user_id"):
            update_payload["user_id"] = system_user_id
        if not row.get("source"):
            update_payload["source"] = provider_ref.get("provider") or (record.get("source") or "canonical")

        if update_payload:
            sb.table("flights").update(update_payload).eq("id", row["id"]).execute()

    else:
        # Create the canonical row with only stable fields
        payload = {
            "user_id": system_user_id,
            "source": provider_ref.get("provider") or (record.get("source") or "canonical"),
            "canonical_hash": c_hash,
            "origin_iata": o,
            "origin_name": record.get("origin_name") or o,
            "destination_iata": d,
            "destination_name": record.get("destination_name") or d,
            "departure_ts": record.get("departure_ts"),
            "arrival_ts": record.get("arrival_ts"),
            "aircraft": record.get("aircraft"),
            "provider_refs": [provider_ref],
        }

        sb.table("flights").upsert(payload, on_conflict="canonical_hash").execute()

def mark_stale(sb) -> None:
    try:
        sb.rpc("mark_stale_flights", {"p_window": "35 minutes"}).execute()
        print("🧹 Marked stale flights unavailable.")
    except Exception as e:
        print(f"⚠️  Mark-stale failed: {e}", file=sys.stderr)

def dedupe_by_canonical(records: list[dict]) -> list[dict]:
    """Remove duplicates by canonical flight identity."""
    from common.canonical import canonical_hash
    seen: set[str] = set()
    out: list[dict] = []
    for r in records:
        h = canonical_hash(
            r.get("origin_iata"),
            r.get("destination_iata"),
            r.get("departure_ts"),
            r.get("aircraft"),
        )
        if h in seen:
            continue
        seen.add(h)
        out.append(r)
    return out

# ---------- main ----------
def main():
    load_dotenv()
    build_indexes()

    # Shared Supabase client (reuses service-role key from db.py)
    sb = get_supabase()

    # SYSTEM_USER_ID is already validated in db.py; just reuse it
    if not SYSTEM_USER_ID:
        print("❌ Missing SYSTEM_USER_ID (auth.users.id UUID)", file=sys.stderr)
        sys.exit(1)

    args = parse_args()
    env_debug = os.getenv("SCRAPER_DEBUG", "0") == "1"
    debug = args.debug or env_debug

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
    total_records: list[FlightRecord] = []
    provider_counts: dict[str, int] = {}
    provider_raw_counts: dict[str, int] = {}

    # fetch
    for prov in providers:
        try:
            p0 = time.time()
            recs = run_provider(prov, debug=debug, debug_dir=report_dir if debug else None)
            raw_count = len(recs)
            recs = dedupe_by_canonical(recs)
            uniq_count = len(recs)

            print(f"ℹ️  {prov.capitalize()}: {uniq_count} unique ({raw_count} raw)")
            provider_counts[prov] = uniq_count
            provider_raw_counts[prov] = raw_count

            total_records.extend(recs)
            for r in recs:
                st = str((r.get("status") or "")).lower() or "unknown"
                parsed_status_counts[st] += 1

            durations[prov] = time.time() - p0
        except Exception as e:
            print(f"❌ {prov} fetch error: {e}", file=sys.stderr)
            durations[prov] = time.time() - p0

    print(f"ℹ️  Total {len(total_records)} unique Datapoints.")

    # write (unless dry-run)

    snapshots_inserted = 0

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

                price_eur = float(r["price_current"]) if isinstance(r.get("price_current"), (int, float)) else None

                # prefer a stable provider label
                provider_name = (r.get("source") or "globeair").strip() or "globeair"

                provider_ref = {
                    "provider": provider_name,
                    "id": r.get("id"),
                    "link": r.get("link_latest") or r.get("link"),
                    "price_eur": price_eur,
                    "currency": r.get("currency") or "EUR",
                    "status": (r.get("status_latest") or r.get("status")),
                    "seen_at": now_utc_iso(),
                }

                # Canonical consolidation write
                upsert_canonical(sb, r, price_eur, c_hash, provider_ref, SYSTEM_USER_ID)

                row = (
                    sb.table("flights")
                    .select("id")
                    .eq("canonical_hash", c_hash)
                    .limit(1)
                    .execute()
                    .data
                )
                if row:
                    flight_id = row[0]["id"]

                    # Insert snapshot matching your table schema
                    status_norm = "available" if (isinstance(price_eur, (int, float)) and price_eur > 0) else "pending"

                    snap_payload = {
                        "flight_id": flight_id,
                        "price_current": price_eur,   # may be None; OK
                        "price_normal": None,         # or coerce from r.get("price_normal")
                        "currency": (r.get("currency") or "EUR").upper(),
                        "status": status_norm,
                        "link": provider_ref.get("link"),
                        "raw": r.get("raw"),
                    }

                    try:
                        snap_res = (
                            sb.table("flight_snapshots")
                            .insert(snap_payload)   # no .select(...) here
                            .execute()
                        )
                        if snap_res.data:
                            snapshots_inserted += 1
                        else:
                            print(f"⚠️ Snapshot insert returned no rows (flight_id={flight_id})", file=sys.stderr)
                    except Exception as e:
                        print(f"❌ Snapshot insert failed (flight_id={flight_id}): {e}", file=sys.stderr)
                else:
                    print(f"⚠️ No canonical row found after upsert for hash={c_hash}", file=sys.stderr)

                saved += 1
                st = str((r.get("status") or "")).lower() or "unknown"
                saved_status_counts[st] += 1

            except Exception as e:
                oc = r.get("origin_iata")
                dc = r.get("destination_iata")
                msg = f"{oc or '??'}→{dc or '??'} — {e}"
                save_errors.append(msg)
                print(f"❌ Fehler für {oc}→{dc}: {e}", file=sys.stderr)

    # Mark stale flights after all snapshots for this run are in
    if not args.dry_run:
        mark_stale(sb)

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
            uniq = provider_counts.get(k, 0)
            raw  = provider_raw_counts.get(k, 0)
            lines.append(f"  - {k}: {uniq} unique / {raw} raw (in {durations.get(k, 0.0):.2f}s)")

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
        print(f"✅ Saved flights: {sum(saved_status_counts.values())} — snapshots: {snapshots_inserted} — statuses: {dict(saved_status_counts)}")


if __name__ == "__main__":
    main()