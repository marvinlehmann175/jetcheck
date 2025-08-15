# tools/backfill_airport_tz.py
import os, time, math
from supabase import create_client
from timezonefinder import TimezoneFinder

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

PAGE_SIZE = 1000      # rows to scan per page from DB
UPDATE_BATCH = 200    # how many per update loop (keeps round-trips reasonable)
SLEEP = 0.15          # small pause between pages to be gentle on rate limits

def needs_tz_value(v):
    return v is None or str(v).strip() in ("", "None", "none", "NULL", "null")

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Missing SUPABASE_URL / SUPABASE_*KEY")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    tf = TimezoneFinder(in_memory=True)

    # total count of rows needing tz
    total_to_update = (
        sb.table("airports")
        .select("id", count="exact")
        .or_("tz.is.null,tz.eq.None,tz.eq.none,tz.eq.NULL,tz.eq.null,tz.eq.")
        .execute()
        .count
    ) or 0

    print(f"Found {total_to_update} airports needing tz update")
    if total_to_update == 0:
        print("✅ Nothing to do.")
        return

    total_updated = 0
    page = 0

    while True:
        start = page * PAGE_SIZE
        end   = start + PAGE_SIZE - 1

        res = (
            sb.table("airports")
            .select("id,iata,icao,lat,lon,tz")
            .or_("tz.is.null,tz.eq.None,tz.eq.none,tz.eq.NULL,tz.eq.null,tz.eq.")
            .order("id", desc=False)
            .range(start, end)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break

        # Compute tz for rows that have coordinates
        updates = []
        for r in rows:
            if not needs_tz_value(r.get("tz")):
                continue
            lat, lon = r.get("lat"), r.get("lon")
            if lat is None or lon is None:
                continue
            try:
                tz = tf.timezone_at(lat=float(lat), lng=float(lon))
            except Exception:
                tz = None
            if tz:
                updates.append({"id": r["id"], "tz": tz})

        # Safety: only update ids that exist/are visible (avoids “insert with null columns”)
        if updates:
            ids = [u["id"] for u in updates]
            existing_res = (
                sb.table("airports")
                .select("id")
                .in_("id", ids)
                .execute()
            )
            existing_ids = {row["id"] for row in (existing_res.data or [])}
            updates = [u for u in updates if u["id"] in existing_ids]

        # Apply updates in small batches using UPDATE (not upsert)
        for i in range(0, len(updates), UPDATE_BATCH):
            chunk = updates[i:i+UPDATE_BATCH]
            for u in chunk:
                try:
                    sb.table("airports").update({"tz": u["tz"]}).eq("id", u["id"]).execute()
                except Exception as e:
                    # keep going; print once per problem row
                    print(f"⚠️  Failed updating id={u['id']}: {e}")

        total_updated += len(updates)
        page += 1

        pct = (total_updated / total_to_update * 100) if total_to_update else 0
        print(f"[Page {page}] Updated {len(updates)} this page — Total: {total_updated}/{total_to_update} ({pct:.1f}%)")

        time.sleep(SLEEP)

    print(f"✅ Done — updated tz for {total_updated} airports")

if __name__ == "__main__":
    main()