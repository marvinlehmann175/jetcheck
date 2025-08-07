"use client";

import { useEffect, useState } from "react";
import FlightCard from "@/components/FlightCard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  const [globeair, setGlobeair] = useState([]);
  const [asl, setAsl] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("globeair"); // "globeair" | "asl"
  const [error, setError] = useState("");

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

  const flights = tab === "globeair" ? globeair : asl;

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

      <section className="content">
        {loading && <div className="skeleton">Lade Flüge…</div>}
        {!loading && error && <div className="notice notice--error">{error}</div>}
        {!loading && !error && flights.length === 0 && (
          <div className="notice">Aktuell keine Flüge verfügbar.</div>
        )}

        <div className="grid">
          {flights.map((f) => (
            <FlightCard key={f.id || `${f.route}-${f.time}-${f.price}`} flight={f} />
          ))}
        </div>
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