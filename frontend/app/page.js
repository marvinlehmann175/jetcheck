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
    <main style={{ padding: "2rem" }}>
      <h1>JetCheck – Verfügbare Leerflüge</h1>

      <h2>✈️ GlobeAir</h2>
      <ul>
        {globeairFlights.map((flight, index) => (
          <li key={`globeair-${index}`}>
            <strong>{flight.route}</strong><br />
            <em>{flight.details}</em><br />
            {flight.link && <a href={flight.link}>Jetzt buchen</a>}
          </li>
        ))}
      </ul>

      <h2>🛩 ASL</h2>
      <ul>
        {aslFlights.map((flight, index) => (
          <li key={`asl-${index}`}>
            <strong>{flight.route}</strong><br />
            <em>
              {flight.date} – {flight.time} – {flight.passengers}
            </em><br />
            <span>{flight.aircraft}</span><br />
            {flight.link && <a href={flight.link}>Jetzt buchen</a>}
          </li>
        ))}
      </ul>
    </main>
  );
}