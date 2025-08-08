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
  const [sortKey, setSortKey] = useState("departure"); // departure | price | seen
  const [sortDir, setSortDir] = useState("asc");

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
      typeof pCurrent === "number" ? pCurrent :
      typeof pNormal === "number" ? pNormal :
      NaN;
    return Number.isFinite(val) ? val : Number.POSITIVE_INFINITY;
  };

  const filtered = useMemo(() => {
    const qLower = q.trim().toLowerCase();
    const fromLower = from.trim().toLowerCase();
    const toLower = to.trim().toLowerCase();
    const dateNorm = date.trim(); // YYYY-MM-DD

    return (flights || []).filter((f) => {
      const oName = (f.origin_name || "").toLowerCase();
      const dName = (f.destination_name || "").toLowerCase();
      const oIata = (f.origin_iata || "").toLowerCase();
      const dIata = (f.destination_iata || "").toLowerCase();

      // Textsuche über beide Orte + IATA
      if (
        qLower &&
        !(
          oName.includes(qLower) ||
          dName.includes(qLower) ||
          oIata.includes(qLower) ||
          dIata.includes(qLower)
        )
      ) {
        return false;
      }

      if (fromLower && !(oName.includes(fromLower) || oIata.includes(fromLower))) {
        return false;
      }
      if (toLower && !(dName.includes(toLower) || dIata.includes(toLower))) {
        return false;
      }

      if (dateNorm) {
        const depDate = (f.departure_ts || "").slice(0, 10); // YYYY-MM-DD
        if (depDate !== dateNorm) return false;
      }

      if (maxPrice) {
        const max = Number(maxPrice);
        if (!Number.isNaN(max)) {
          const p = priceToNumber(f.price_current, f.price_normal);
          if (p > max) return false;
        }
      }

      return true;
    });
  }, [flights, q, from, to, date, maxPrice]);

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
            placeholder="Suche… (Ort oder IATA, z. B. Ibiza / IBZ)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </section>

      {/* Controls */}
      <section className="controls">
        <input
          className="input"
          placeholder="Abflug (Ort/IATA, z. B. IBZ)"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
        />
        <input
          className="input"
          placeholder="Ziel (Ort/IATA, z. B. ZRH)"
          value={to}
          onChange={(e) => setTo(e.target.value)}
        />
        <input
          className="input"
          type="date"
          placeholder="Datum (YYYY-MM-DD)"
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
            <option value="departure">Abflugzeit</option>
            <option value="price">Preis</option>
            <option value="seen">Zuletzt gesehen</option>
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
                    <FlightCard key={f.id} flight={f} />
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