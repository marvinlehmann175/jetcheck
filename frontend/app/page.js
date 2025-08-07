"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [flights, setFlights] = useState([]);

  useEffect(() => {
    fetch("http://localhost:5000/api/globeair")
      .then((res) => res.json())
      .then(setFlights);
  }, []);

  return (
    <main>
      <h1>JetCheck – Verfügbare Leerflüge</h1>
      <ul>
        {flights.map((flight, index) => (
          <li key={index}>
            <strong>{flight.route}</strong><br />
            <em>{flight.details}</em><br />
            {flight.link && <a href={flight.link}>Jetzt buchen</a>}
          </li>
        ))}
      </ul>
    </main>
  );
}
