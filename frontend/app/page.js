"use client";

import { useEffect, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5000";

export default function Home() {
  const [globeairFlights, setGlobeairFlights] = useState([]);
  const [aslFlights, setAslFlights] = useState([]);

  const [loadingGlobeair, setLoadingGlobeair] = useState(true);
  const [loadingAsl, setLoadingAsl] = useState(true);

  const [errorGlobeair, setErrorGlobeair] = useState("");
  const [errorAsl, setErrorAsl] = useState("");

  useEffect(() => {
    // GlobeAir
    fetch(`${API_BASE}/api/globeair`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setGlobeairFlights(Array.isArray(data) ? data : []))
      .catch((err) => {
        console.error("GlobeAir fetch error:", err);
        setErrorGlobeair("Konnte GlobeAir-Daten nicht laden.");
      })
      .finally(() => setLoadingGlobeair(false));

    // ASL (derzeit evtl. leer – bleibt vorbereitet)
    fetch(`${API_BASE}/api/asl`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setAslFlights(Array.isArray(data) ? data : []))
      .catch((err) => {
        console.error("ASL fetch error:", err);
        setErrorAsl("Konnte ASL-Daten nicht laden.");
      })
      .finally(() => setLoadingAsl(false));
  }, []);

  return (
    <main style={styles.container}>
      <h1 style={styles.title}>JetCheck – Verfügbare Leerflüge</h1>

      {/* GlobeAir */}
      <section>
        <h2 style={styles.sectionTitle}>✈️ GlobeAir</h2>

        {loadingGlobeair ? (
          <p>lade…</p>
        ) : errorGlobeair ? (
          <p style={styles.error}>{errorGlobeair}</p>
        ) : globeairFlights.length === 0 ? (
          <p>Aktuell keine Flüge.</p>
        ) : (
          <div style={styles.grid}>
            {globeairFlights.map((f, i) => (
              <div key={`globeair-${f.id ?? i}`} style={styles.card}>
                <h3 style={{ marginTop: 0 }}>{f.route}</h3>
                <p style={{ margin: "0.25rem 0" }}>
                  <strong>{f.date}</strong> • {f.time}
                </p>
                {f.price && (
                  <p style={{ margin: "0.25rem 0" }}>{f.price}</p>
                )}
                {f.probability && (
                  <p style={{ margin: "0.25rem 0", opacity: 0.7 }}>
                    Probability: {f.probability}
                  </p>
                )}
                {f.link && (
                  <a
                    href={f.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.button}
                  >
                    Jetzt buchen →
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ASL */}
      <section>
        <h2 style={styles.sectionTitle}>🛩 ASL</h2>

        {loadingAsl ? (
          <p>lade…</p>
        ) : errorAsl ? (
          <p style={styles.error}>{errorAsl}</p>
        ) : aslFlights.length === 0 ? (
          <p>Aktuell keine ASL-Flüge.</p>
        ) : (
          <div style={styles.grid}>
            {aslFlights.map((f, i) => (
              <div key={`asl-${f.id ?? i}`} style={styles.card}>
                <h3 style={{ marginTop: 0 }}>{f.route}</h3>
                <p style={{ margin: "0.25rem 0" }}>
                  <strong>{f.date}</strong> • {f.time}
                </p>
                {f.passengers && (
                  <p style={{ margin: "0.25rem 0" }}>
                    {f.passengers} Personen
                  </p>
                )}
                {f.aircraft && (
                  <p style={{ margin: "0.25rem 0" }}>
                    Flugzeugtyp: {f.aircraft}
                  </p>
                )}
                {f.link && (
                  <a
                    href={f.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.button}
                  >
                    Jetzt buchen →
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

const styles = {
  container: {
    maxWidth: "1000px",
    margin: "0 auto",
    padding: "2rem",
    fontFamily: "Arial, sans-serif",
    backgroundColor: "#f5f7fa",
  },
  title: {
    textAlign: "center",
    marginBottom: "3rem",
    fontSize: "2.5rem",
    color: "#1e2a38",
  },
  sectionTitle: {
    fontSize: "1.8rem",
    marginBottom: "1rem",
    color: "#333",
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: "1.5rem",
    marginBottom: "3rem",
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: "10px",
    padding: "1.5rem",
    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
  },
  button: {
    display: "inline-block",
    marginTop: "1rem",
    padding: "0.5rem 1rem",
    backgroundColor: "#1e2a38",
    color: "#fff",
    textDecoration: "none",
    borderRadius: "5px",
  },
  error: {
    color: "#b00020",
  },
};