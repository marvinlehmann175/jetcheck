"use client";

import { useEffect, useMemo, useState } from "react";
import FlightCard from "../components/FlightCard.jsx";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  const [globeair, setGlobeair] = useState([]);
  const [asl, setAsl] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Suche/Filter & Sortierung (lassen wir drin)
  const [q, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [date, setDate] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sortKey, setSortKey] = useState("date");
  const [sortDir, setSortDir] = useState("asc");

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [gaRes, aslRes] = await Promise.allSettled([
          fetch(`${API_BASE}/api/globeair`, { cache: "no-store" }),
          fetch(`${API_BASE}/api/asl`, { cache: "no-store" }),
        ]);
        if (cancelled) return;

        if (gaRes.status === "fulfilled") {
          const data = await gaRes.value.json();
          setGlobeair(
            (Array.isArray(data) ? data : []).map((d) => ({
              ...d,
              source: "GlobeAir",
            }))
          );
        } else {
          console.error("GlobeAir fetch error:", gaRes.reason);
          setError("Fehler beim Laden der GlobeAir-Daten.");
        }

        if (aslRes.status === "fulfilled") {
          const data = await aslRes.value.json();
          setAsl(
            (Array.isArray(data) ? data : []).map((d) => ({
              ...d,
              source: "ASL",
            }))
          );
        } else {
          console.error("ASL fetch error:", aslRes.reason);
        }
      } catch (e) {
        console.error(e);
        setError("Unerwarteter Fehler beim Laden der Daten.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const rawFlights = useMemo(() => {
    // Beide Quellen in eine Liste
    return [...globeair, ...asl];
  }, [globeair, asl]);

  const priceToNumber = (price) => {
    if (!price) return Number.POSITIVE_INFINITY;
    const cleaned = String(price)
      .replace(/[^\d.,]/g, "")
      .replace(/\./g, "")
      .replace(",", ".");
    const num = Number.parseFloat(cleaned);
    return Number.isNaN(num) ? Number.POSITIVE_INFINITY : num;
    // Optional: wenn "Book for €990" kommt, wird oben automatisch 990 erkannt
  };

  const filtered = useMemo(() => {
    const qLower = q.trim().toLowerCase();
    const fromLower = from.trim().toLowerCase();
    const toLower = to.trim().toLowerCase();
    const dateNorm = date.trim();

    return (rawFlights || []).filter((f) => {
      const route = (f.route || "").toLowerCase();
      const [dep, arr] = (f.route || "")
        .split("→")
        .map((s) => s?.trim().toLowerCase());
      const d = (f.date || "").trim();

      if (qLower && !route.includes(qLower)) return false;
      if (fromLower && !(dep || "").includes(fromLower)) return false;
      if (toLower && !(arr || "").includes(toLower)) return false;
      if (dateNorm && d !== dateNorm) return false;

      if (maxPrice) {
        const max = Number(maxPrice);
        if (!Number.isNaN(max) && priceToNumber(f.price) > max) return false;
      }

      return true;
    });
  }, [rawFlights, q, from, to, date, maxPrice]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let A, B;
      switch (sortKey) {
        case "price":
          A = priceToNumber(a.price);
          B = priceToNumber(b.price);
          break;
        case "time":
          A = a.time || "";
          B = b.time || "";
          break;
        case "date":
        default:
          A = a.date || "";
          B = b.date || "";
          break;
      }
      if (A < B) return sortDir === "asc" ? -1 : 1;
      if (A > B) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const total = sorted.length;
  const pageSizeClamped = pageSize;
  const totalPages = Math.max(1, Math.ceil(total / pageSizeClamped));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSizeClamped;
    return sorted.slice(start, start + pageSizeClamped);
  }, [sorted, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [q, from, to, date, maxPrice, sortKey, sortDir]);

  return (
    <main className="screen">
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          <span className="logo">JetCheck</span>
        </div>
      </header>

      <section className="hero">
        <h1>Exklusive Leerflüge in Echtzeit</h1>
        <p>Finde verfügbare Empty Legs mit nur einem Klick.</p>
        <div className="searchbar">
          <input
            className="searchbar__input"
            placeholder="Suche Route… (z. B. Ibiza oder ZRH)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </section>

      {/* Controls */}
      <section className="controls">
        <input
          className="input"
          placeholder="Abflug (z. B. IBZ)"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
        />
        <input
          className="input"
          placeholder="Ziel (z. B. ZRH)"
          value={to}
          onChange={(e) => setTo(e.target.value)}
        />
        <input
          className="input"
          placeholder="Datum exakt (wie in der Karte)"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <input
          className="input"
          type="number"
          placeholder="Max. Preis (€)"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
        />

        <div className="selects">
          <select
            className="select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
          >
            <option value="date">Datum</option>
            <option value="time">Zeit</option>
            <option value="price">Preis</option>
          </select>
          <select
            className="select"
            value={sortDir}
            onChange={(e) => setSortDir(e.target.value)}
          >
            <option value="asc">Aufsteigend</option>
            <option value="desc">Absteigend</option>
          </select>
        </div>
      </section>

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
              <div className="notice">
                Keine Flüge für die aktuelle Filterung.
              </div>
            ) : (
              <>
                <div className="grid">
                  {pageItems.map((f) => (
                    <FlightCard
                      key={f.id || `${f.route}-${f.time}-${f.price}`}
                      flight={f}
                    />
                  ))}
                </div>

                <div className="pager">
                  <button
                    className="btn"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    ◀︎ Zurück
                  </button>
                  <div className="pager__info">
                    Seite {currentPage} / {totalPages} · {total} Ergebnisse
                  </div>
                  <button
                    className="btn"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Weiter ▶︎
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
