"use client";

import { useEffect, useMemo, useState } from "react";
import FlightCard from "../components/FlightCard.jsx";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  const [flights, setFlights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Suche/Filter & Sortierung
  const [q, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [date, setDate] = useState(""); // YYYY-MM-DD
  const [maxPrice, setMaxPrice] = useState("");
  const [status, setStatus] = useState("");
  const [sortKey, setSortKey] = useState("departure"); // departure | price | seen
  const [sortDir, setSortDir] = useState("asc");

  // Unique airports: show "IATA — Name", value=IATA (stable & short)
  const departureOptions = useMemo(() => {
    const set = new Map(); // key by IATA
    for (const f of flights) {
      const code = (f.origin_iata || "").toUpperCase();
      if (!code) continue;
      if (
        status &&
        String(f.status_latest ?? f.status ?? "").toLowerCase() !==
          status.toLowerCase()
      )
        continue;
      // If a destination is chosen, only include origins that actually pair with it
      if (to) {
        const destCode = to.toUpperCase();
        if ((f.destination_iata || "").toUpperCase() !== destCode) continue;
      }
      const name = f.origin_name || code;
      if (!set.has(code)) set.set(code, `${code} — ${name}`);
    }
    return Array.from(set, ([value, label]) => ({ value, label })).sort(
      (a, b) => a.label.localeCompare(b.label)
    );
  }, [flights, status, to]);

  const destinationOptions = useMemo(() => {
    const set = new Map(); // key by IATA
    for (const f of flights) {
      const code = (f.destination_iata || "").toUpperCase();
      if (!code) continue;
      if (
        status &&
        String(f.status_latest ?? f.status ?? "").toLowerCase() !==
          status.toLowerCase()
      )
        continue;
      // If a departure is chosen, only include destinations reachable from it
      if (from) {
        const depCode = from.toUpperCase();
        if ((f.origin_iata || "").toUpperCase() !== depCode) continue;
      }
      const name = f.destination_name || code;
      if (!set.has(code)) set.set(code, `${code} — ${name}`);
    }
    return Array.from(set, ([value, label]) => ({ value, label })).sort(
      (a, b) => a.label.localeCompare(b.label)
    );
  }, [flights, status, from]);

  // Drawer UI
  const [showFilters, setShowFilters] = useState(false);
  const activeFilters = useMemo(() => {
    let n = 0;
    if (from.trim()) n++;
    if (to.trim()) n++;
    if (date.trim()) n++;
    if (String(maxPrice).trim()) n++;
    if (status.trim()) n++;
    return n;
  }, [from, to, date, maxPrice, status]);
  const resetFilters = () => {
    setFrom("");
    setTo("");
    setDate("");
    setMaxPrice("");
    setStatus("");
  };

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/api/flights`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!cancelled) {
          setFlights(Array.isArray(data) ? data : []);
        }
      } catch (e) {
        console.error(e);
        if (!cancelled) setError("Fehler beim Laden der Flüge.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const priceToNumber = (pCurrent, pNormal) => {
    const val =
      typeof pCurrent === "number"
        ? pCurrent
        : typeof pNormal === "number"
        ? pNormal
        : NaN;
    return Number.isFinite(val) ? val : Number.POSITIVE_INFINITY;
  };

const filtered = useMemo(() => {
  const qLower = q.trim().toLowerCase();
  const dateNorm = date.trim(); // YYYY-MM-DD

  return (flights || []).filter((f) => {
    const oName = (f.origin_name || "").toLowerCase();
    const dName = (f.destination_name || "").toLowerCase();
    const oIataLower = (f.origin_iata || "").toLowerCase();
    const dIataLower = (f.destination_iata || "").toLowerCase();

    const depTs = f.departure_ts ? new Date(f.departure_ts).getTime() : 0;
    if (depTs && depTs < Date.now()) return false;

    // Free-text search over names + IATA (substring)
    if (
      qLower &&
      !(
        oName.includes(qLower) ||
        dName.includes(qLower) ||
        oIataLower.includes(qLower) ||
        dIataLower.includes(qLower)
      )
    ) {
      return false;
    }

    // Exact IATA match for dropdowns
    const oIata = (f.origin_iata || "").toUpperCase();
    const dIata = (f.destination_iata || "").toUpperCase();
    if (from && oIata !== from.toUpperCase()) return false;
    if (to && dIata !== to.toUpperCase()) return false;

    if (dateNorm) {
      const depDate = (f.departure_ts || "").slice(0, 10); // YYYY-MM-DD
      if (depDate !== dateNorm) return false;
    }

    if (maxPrice) {
      const max = Number(maxPrice);
      if (!Number.isNaN(max)) {
        const p =
          typeof f.price_current === "number"
            ? f.price_current
            : typeof f.price_normal === "number"
            ? f.price_normal
            : Number.POSITIVE_INFINITY;
        if (p > max) return false;
      }
    }

    if (status) {
      const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
      if (s !== status.toLowerCase()) return false;
    }

    return true;
  });
}, [flights, q, from, to, date, maxPrice, status]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let A, B;
      switch (sortKey) {
        case "price":
          A = priceToNumber(a.price_current, a.price_normal);
          B = priceToNumber(b.price_current, b.price_normal);
          break;
        case "seen":
          A = a.last_seen_at || "";
          B = b.last_seen_at || "";
          break;
        case "departure":
        default:
          A = a.departure_ts || "";
          B = b.departure_ts || "";
          break;
      }
      if (A < B) return sortDir === "asc" ? -1 : 1;
      if (A > B) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [q, from, to, date, maxPrice, status, sortKey, sortDir]);

  return (
    <main className="screen">
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          <span className="logo">JetCheck</span>
        </div>
      </header>

      <section className="hero">
        <h1>Exclusive Empty Legs in Real Time</h1>
        <p>Find available empty legs with just one click.</p>
        <div className="searchbar">
          <input
            className="searchbar__input"
            placeholder="Search for (Location or IATA, e.g. Ibiza / IBZ)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </section>

      {/* Controls Top Bar (Sort + Filter Button) */}
      <section className="controls-bar">
        <div className="controls-bar__inner">
          <button
            className="btn btn-filter"
            onClick={() => setShowFilters(true)}
            aria-expanded={showFilters ? "true" : "false"}
            aria-controls="filters-drawer"
          >
            🔎 Filter {activeFilters > 0 ? `(${activeFilters})` : ""}
          </button>

          <div className="selects">
            <select
              className="select"
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value)}
            >
              <option value="departure">Departure Time</option>
              <option value="price">Price</option>
              <option value="seen">Last Seen</option>
            </select>
            <select
              className="select"
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value)}
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        </div>
      </section>

      {/* Drawer + Overlay */}
      {showFilters && (
        <div
          className="filters-overlay"
          onClick={() => setShowFilters(false)}
          aria-hidden="true"
        />
      )}
      <aside
        id="filters-drawer"
        className={`filters-drawer ${showFilters ? "open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="filters-title"
      >
        <div className="filters-header">
          <h2 id="filters-title">Filters</h2>
          <button
            className="btn btn-close"
            onClick={() => setShowFilters(false)}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <form
          className="filters-form"
          onSubmit={(e) => {
            e.preventDefault();
            setShowFilters(false);
          }}
        >
          <label className="label">
            Status
            <select
              className="select"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">All</option>
              <option value="available">Available</option>
              <option value="pending">Pending</option>
            </select>
          </label>
          <label className="label">
            Departure (City/IATA)
            <select
              className="select"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
                // When changing departure, keep destination only if still valid
                if (e.target.value && to) {
                  const stillValid = destinationOptions.some(
                    (o) => o.value === to
                  );
                  if (!stillValid) setTo("");
                }
              }}
            >
              <option value="">Any</option>
              {departureOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="label">
            Destination (City/IATA)
            <select
              className="select"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
                // When changing destination, keep departure only if still valid
                if (e.target.value && from) {
                  const stillValid = departureOptions.some(
                    (o) => o.value === from
                  );
                  if (!stillValid) setFrom("");
                }
              }}
            >
              <option value="">Any</option>
              {destinationOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="label">
            Date
            <input
              className="input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>

          <label className="label">
            Max Price (€)
            <input
              className="input"
              type="number"
              inputMode="numeric"
              placeholder="e.g. 15000"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </label>

          <div className="filters-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={resetFilters}
            >
              Reset
            </button>
            <button type="submit" className="btn btn-primary">
              Apply
            </button>
          </div>
        </form>
      </aside>

      <section className="content">
        {loading && (
          <div className="grid">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="card skeleton-block" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="notice notice--error">{error}</div>
        )}

        {!loading && !error && (
          <>
            {sorted.length === 0 ? (
<div className="notice">No flights for the current filters.</div>
            ) : (
              <>
                <div className="grid">
                  {pageItems.map((f) => (
                    <FlightCard key={f.id} flight={f} />
                  ))}
                </div>

                <div className="pager">
                  <button
                    className="btn"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    ◀︎ Back
                  </button>
                  <div className="pager__info">
                    Page {currentPage} / {totalPages} · {total} results
                  </div>
                  <button
                    className="btn"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next ▶︎
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </section>

      <footer className="footer">
        <span>© {new Date().getFullYear()} JetCheck</span>
        <span className="sep">•</span>
        <a
          href="https://jetcheck-eight.vercel.app"
          target="_blank"
          rel="noreferrer"
        >
          Live
        </a>
      </footer>
    </main>
  );
}
