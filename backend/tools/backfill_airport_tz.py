# tools/backfill_airport_tz.py
import os, time
from supabase import create_client
from timezonefinder import TimezoneFinder

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

BATCH = 1000
SLEEP = 0.2  # seconds between pages

def needs_tz_value(v):
    return v is None or str(v).strip() in ("", "None", "none", "NULL", "null")

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit("Missing SUPABASE_URL / SUPABASE_*KEY")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    tf = TimezoneFinder(in_memory=True)

    # Get total number of airports needing tz
    total_to_update = (
        sb.table("airports")
        .select("id", count="exact")
        .or_("tz.is.null,tz.eq.None,tz.eq.none,tz.eq.NULL,tz.eq.null,tz.eq.")
        .execute()
        .count
    )
    print(f"Found {total_to_update} airports needing tz update")

    total_updated = 0
    page = 0

    while True:
        start = page * BATCH
        end   = start + BATCH - 1

        q = (sb.table("airports")
               .select("id,iata,icao,lat,lon,tz")
               .or_("tz.is.null,tz.eq.None,tz.eq.none,tz.eq.NULL,tz.eq.null,tz.eq.")
               .order("id", desc=False)
               .range(start, end))

        res = q.execute()
        rows = res.data or []
        if not rows:
            break

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

        for i in range(0, len(updates), 500):
            chunk = updates[i:i+500]
            if not chunk:
                continue
            sb.table("airports").upsert(chunk, on_conflict="id").execute()

        total_updated += len(updates)
        page += 1

        percent = (total_updated / total_to_update * 100) if total_to_update else 0
        print(f"[Page {page}] Updated {len(updates)} this page — Total: {total_updated}/{total_to_update} ({percent:.1f}%)")

        time.sleep(SLEEP)

    print(f"✅ Done — updated tz for {total_updated} airports")

if __name__ == "__main__":
    main()