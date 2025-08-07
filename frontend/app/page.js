"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [globeairFlights, setGlobeairFlights] = useState([]);
  const [aslFlights, setAslFlights] = useState([]);

  useEffect(() => {
    fetch("https://jetcheck.onrender.com/api/globeair")
      .then((res) => res.json())
      .then(setGlobeairFlights);

    fetch("https://jetcheck.onrender.com/api/asl")
      .then((res) => res.json())
      .then(setAslFlights);
  }, []);

  return (
    <main style={styles.container}>
      <h1 style={styles.title}>JetCheck – Verfügbare Leerflüge</h1>

      <section>
        <h2 style={styles.sectionTitle}>✈️ GlobeAir</h2>
        <div style={styles.grid}>
          {globeairFlights.map((flight, index) => (
            <div key={`globeair-${index}`} style={styles.card}>
              <h3>{flight.route}</h3>
              <p>{flight.details}</p>
              {flight.link && (
                <a href={flight.link} target="_blank" rel="noopener noreferrer" style={styles.button}>
                  Jetzt buchen
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 style={styles.sectionTitle}>🛩 ASL</h2>
        <div style={styles.grid}>
          {aslFlights.map((flight, index) => (
            <div key={`asl-${index}`} style={styles.card}>
              <h3>{flight.route}</h3>
              <p>
                {flight.date} – {flight.time}<br />
                {flight.passengers} Personen
              </p>
              <p>Flugzeugtyp: {flight.aircraft}</p>
              {flight.link && (
                <a href={flight.link} target="_blank" rel="noopener noreferrer" style={styles.button}>
                  Jetzt buchen
                </a>
              )}
            </div>
          ))}
        </div>
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
};