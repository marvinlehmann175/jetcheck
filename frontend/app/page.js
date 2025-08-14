"use client";

import { useEffect, useMemo, useState } from "react";
import FlightCard from "../components/FlightCard.jsx";
import FiltersDrawer from "../components/FiltersDrawer.jsx";
import { messages } from "./i18n";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  // --- i18n ---------------------------------------------------------------
  const [lang] = useState("en"); // <- set your default language code here
  const dict = messages?.[lang] || {};
  const tt = (k, fb) => (dict[k] ?? fb); // simple safe getter

  // --- data + ui state ----------------------------------------------------
  const [flights, setFlights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [status, setStatus] = useState(""); // "", "available", "pending"
  const [from, setFrom] = useState("");     // IATA
  const [to, setTo] = useState("");         // IATA
  const [date, setDate] = useState("");     // YYYY-MM-DD
  const [maxPrice, setMaxPrice] = useState("");
  const [aircraft, setAircraft] = useState("");

  // Sort/pagination
  const [sortKey, setSortKey] = useState("departure"); // "departure" | "price" | "seen"
  const [sortDir, setSortDir] = useState("asc");       // "asc" | "desc"
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Drawer
  const [showFilters, setShowFilters] = useState(false);

  // --- fetch --------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/api/flights`, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) setFlights(Array.isArray(data) ? data : []);
      } catch (e) {
        console.error(e);
        if (!cancelled) setError(tt("error.load", "Failed to load flights."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []); // once

  // --- helpers ------------------------------------------------------------
  const priceToNumber = (pCurrent, pNormal) => {
    const val =
      typeof pCurrent === "number"
        ? pCurrent
        : typeof pNormal === "number"
        ? pNormal
        : NaN;
    return Number.isFinite(val) ? val : Number.POSITIVE_INFINITY;
  };

  // Options for dropdowns (filtered to “currently possible”)
  const departureOptions = useMemo(() => {
    const m = new Map();
    for (const f of flights) {
      const code = (f.origin_iata || "").toUpperCase();
      if (!code) continue;
      // keep only pairs that match selected destination/status (if any)
      if (to && (f.destination_iata || "").toUpperCase() !== to.toUpperCase()) continue;
      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) continue;
      }
      const name = f.origin_name || code;
      if (!m.has(code)) m.set(code, `${code} — ${name}`);
    }
    return Array.from(m, ([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [flights, status, to]);

  const destinationOptions = useMemo(() => {
    const m = new Map();
    for (const f of flights) {
      const code = (f.destination_iata || "").toUpperCase();
      if (!code) continue;
      if (from && (f.origin_iata || "").toUpperCase() !== from.toUpperCase()) continue;
      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) continue;
      }
      const name = f.destination_name || code;
      if (!m.has(code)) m.set(code, `${code} — ${name}`);
    }
    return Array.from(m, ([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [flights, status, from]);

  const aircraftOptions = useMemo(() => {
    const set = new Set();
    for (const f of flights) {
      if (f.aircraft && String(f.aircraft).trim())
        set.add(String(f.aircraft).trim());
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [flights]);

  // Active filters counter (for the Filter button)
  const activeFilters = useMemo(() => {
    let n = 0;
    if (status.trim()) n++;
    if (from.trim()) n++;
    if (to.trim()) n++;
    if (date.trim()) n++;
    if (String(maxPrice).trim()) n++;
    if (aircraft.trim()) n++;
    return n;
  }, [status, from, to, date, maxPrice, aircraft]);

  const resetFilters = () => {
    setStatus("");
    setFrom("");
    setTo("");
    setDate("");
    setMaxPrice("");
    setAircraft("");
  };

  // --- filtering/sorting/paging ------------------------------------------
  const filtered = useMemo(() => {
    return (flights || []).filter((f) => {
      // Hide past flights
      const depMs = f.departure_ts ? new Date(f.departure_ts).getTime() : 0;
      if (depMs && depMs < Date.now()) return false;

      // Status
      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) return false;
      }

      // Departure/Destination by IATA
      if (from && (f.origin_iata || "").toUpperCase() !== from.toUpperCase())
        return false;
      if (to && (f.destination_iata || "").toUpperCase() !== to.toUpperCase())
        return false;

      // Exact date
      if (date) {
        const depDate = (f.departure_ts || "").slice(0, 10);
        if (depDate !== date) return false;
      }

      // Max price
      if (maxPrice) {
        const max = Number(maxPrice);
        if (!Number.isNaN(max)) {
          const p = priceToNumber(f.price_current, f.price_normal);
          if (p > max) return false;
        }
      }

      // Aircraft
      if (aircraft && String(f.aircraft || "") !== aircraft) return false;

      return true;
    });
  }, [flights, status, from, to, date, maxPrice, aircraft]);

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
  useEffect(() => { setPage(1); }, [status, from, to, date, maxPrice, aircraft, sortKey, sortDir]);

  // --- render -------------------------------------------------------------
  return (
    <main className="screen">
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          <span className="logo">JetCheck</span>
        </div>
      </header>

      <section className="hero">
        <h1>{tt("hero.title", "Exclusive Empty Legs in Real Time")}</h1>
        <p>{tt("hero.subtitle", "Find available empty legs with just one click.")}</p>
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
            {tt("filters.button", "🔎 Filters")} {activeFilters > 0 ? `(${activeFilters})` : ""}
          </button>

          <div className="selects">
            <select
              className="select"
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value)}
              aria-label={tt("sort.label", "Sort by")}
            >
              <option value="departure">{tt("sort.departure", "Departure Time")}</option>
              <option value="price">{tt("sort.price", "Price")}</option>
              <option value="seen">{tt("sort.seen", "Last Seen")}</option>
            </select>
            <select
              className="select"
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value)}
              aria-label={tt("sort.direction", "Sort direction")}
            >
              <option value="asc">{tt("sort.asc", "Ascending")}</option>
              <option value="desc">{tt("sort.desc", "Descending")}</option>
            </select>
          </div>
        </div>
      </section>

      {/* Drawer */}
      <FiltersDrawer
        open={showFilters}
        onClose={() => setShowFilters(false)}
        t={tt}
        // values
        status={status}
        from={from}
        to={to}
        date={date}
        maxPrice={maxPrice}
        aircraft={aircraft}
        // setters
        setStatus={setStatus}
        setFrom={setFrom}
        setTo={setTo}
        setDate={setDate}
        setMaxPrice={setMaxPrice}
        setAircraft={setAircraft}
        resetFilters={resetFilters}
        // options
        departureOptions={departureOptions}
        destinationOptions={destinationOptions}
        aircraftOptions={aircraftOptions}
      />

      <section className="content">
        {loading && (
          <div className="grid" role="status" aria-live="polite" aria-busy="true">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="card skeleton-block" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div className="notice notice--error" role="alert" aria-live="assertive">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {sorted.length === 0 ? (
              <div className="notice" role="status" aria-live="polite">
                {tt(
                  "emptyState",
                  "No flights for the current filters. Try changing the date or increasing the max price."
                )}
              </div>
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
                    ◀︎ {tt("pager.back", "Back")}
                  </button>
                  <div className="pager__info">
                    {tt("pager.page", "Page")} {currentPage} / {totalPages} · {total} {tt("pager.results", "results")}
                  </div>
                  <button
                    className="btn"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    {tt("pager.next", "Next")} ▶︎
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
        <a href="https://jetcheck-eight.vercel.app" target="_blank" rel="noreferrer">
          {tt("footer.live", "Live")}
        </a>
      </footer>
    </main>
  );
}