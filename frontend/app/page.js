"use client";

import { useEffect, useMemo, useState } from "react";
import FlightCard from "@/components/FlightCard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  const [globeair, setGlobeair] = useState([]);
  const [asl, setAsl] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("globeair"); // "globeair" | "asl"
  const [error, setError] = useState("");

  // UI State: Suche/Filter
  const [q, setQ] = useState("");             // Freitext (Route)
  const [from, setFrom] = useState("");       // Abflug (IATA oder Stadt)
  const [to, setTo] = useState("");           // Ziel
  const [date, setDate] = useState("");       // exaktes Datum (Stringvergleich)
  const [maxPrice, setMaxPrice] = useState(""); // z.B. 1500

  // Sortierung
  const [sortKey, setSortKey] = useState("date");  // date | time | price
  const [sortDir, setSortDir] = useState("asc");   // asc | desc

  // Pagination
  const [page, setPage] = useState(1);
  const pageSize = 12;

  useEffect(() => {
    async function load() {
      try {
        const [gaRes, aslRes] = await Promise.allSettled([
          fetch(`${API_BASE}/api/globeair`, { cache: "no-store" }),
          fetch(`${API_BASE}/api/asl`, { cache: "no-store" }),
        ]);

        if (gaRes.status === "fulfilled") {
          const data = await gaRes.value.json();
          setGlobeair(Array.isArray(data) ? data : []);
        } else {
          console.error("GlobeAir fetch error:", gaRes.reason);
          setError("Fehler beim Laden der GlobeAir-Daten.");
        }

        if (aslRes.status === "fulfilled") {
          const data = await aslRes.value.json();
          setAsl(Array.isArray(data) ? data : []);
        } else {
          console.error("ASL fetch error:", aslRes.reason);
        }
      } catch (e) {
        console.error(e);
        setError("Unerwarteter Fehler beim Laden der Daten.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Aktive Liste nach Tab
  const rawFlights = tab === "globeair" ? globeair : asl;

  // Helper: Preis als Zahl extrahieren (z. B. "€1,290" -> 1290)
  const priceToNumber = (price) => {
    if (!price) return Number.POSITIVE_INFINITY;
    const cleaned = String(price).replace(/[^\d.,]/g, "").replace(/\./g, "").replace(",", ".");
    const num = Number.parseFloat(cleaned);
    return Number.isNaN(num) ? Number.POSITIVE_INFINITY : num;
  };

  // Filter + Suche
  const filtered = useMemo(() => {
    const qLower = q.trim().toLowerCase();
    const fromLower = from.trim().toLowerCase();
    const toLower = to.trim().toLowerCase();
    const dateNorm = date.trim();

    return (rawFlights || []).filter((f) => {
      const route = (f.route || "").toLowerCase();
      const [dep, arr] = (f.route || "").split("→").map((s) => s?.trim().toLowerCase());
      const d = (f.date || "").trim();

      // Freitext in Route
      if (qLower && !route.includes(qLower)) return false;

      // Abflug-Stichwort
      if (fromLower && !(dep || "").includes(fromLower)) return false;

      // Ziel-Stichwort
      if (toLower && !(arr || "").includes(toLower)) return false;

      // Exaktes Datum (string match; später gerne auf ISO-Datum umstellen)
      if (dateNorm && d !== dateNorm) return false;

      // Preislimit
      if (maxPrice) {
        const max = Number(maxPrice);
        if (!Number.isNaN(max) && priceToNumber(f.price) > max) return false;
      }

      return true;
    });
  }, [rawFlights, q, from, to, date, maxPrice]);

  // Sortierung
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
          A = (a.time || "");
          B = (b.time || "");
          break;
        case "date":
        default:
          A = (a.date || "");
          B = (b.date || "");
          break;
      }
      if (A < B) return sortDir === "asc" ? -1 : 1;
      if (A > B) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  // Pagination
  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, currentPage]);

  // Reset auf Seite 1, wenn Filter/Tab wechseln
  useEffect(() => {
    setPage(1);
  }, [tab, q, from, to, date, maxPrice, sortKey, sortDir]);

  return (
    <main className="screen">
      <header className="topbar">
        <div className="brand">
          <span className="dot" />
          <span className="logo">JetCheck</span>
        </div>
        <nav className="tabs">
          <button
            className={`tab ${tab === "globeair" ? "is-active" : ""}`}
            onClick={() => setTab("globeair")}
          >
            ✈️ GlobeAir
          </button>
          <button
            className={`tab ${tab === "asl" ? "is-active" : ""}`}
            onClick={() => setTab("asl")}
          >
            🛩 ASL
          </button>
        </nav>
      </header>

      <section className="hero">
        <h1>Exklusive Leerflüge in Echtzeit</h1>
        <p>Finde verfügbare Empty Legs mit nur einem Klick.</p>
      </section>

      {/* Controls */}
      <section className="controls">
        <input
          className="input"
          placeholder="Suche Route… (z. B. Ibiza oder ZRH)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
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
          <select className="select" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
            <option value="date">Datum</option>
            <option value="time">Zeit</option>
            <option value="price">Preis</option>
          </select>
          <select className="select" value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
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

        {!loading && error && <div className="notice notice--error">{error}</div>}

        {!loading && !error && (
          <>
            {sorted.length === 0 ? (
              <div className="notice">Keine Flüge für die aktuelle Filterung.</div>
            ) : (
              <>
                <div className="grid">
                  {pageItems.map((f) => (
                    <FlightCard key={f.id || `${f.route}-${f.time}-${f.price}`} flight={f} />
                  ))}
                </div>

                {/* Pagination */}
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
        <a href="https://jetcheck-eight.vercel.app" target="_blank" rel="noreferrer">
          Live
        </a>
      </footer>
    </main>
  );
}