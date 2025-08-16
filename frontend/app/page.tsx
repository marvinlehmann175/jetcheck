'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import FlightCard from '@/components/FlightCard';
import { messages } from "./i18n.js";
import { useI18n } from "@/app/_providers/I18nProvider";

export default function Home() {
  const [flights, setFlights] = useState<any[] | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5001';
        const res = await fetch(`${base}/api/flights?page_size=6&sort_key=departure_ts&sort_dir=asc`, { cache: 'no-store' });
        const data = await res.json();
        setFlights(Array.isArray(data) ? data : []);
      } catch {
        setFlights([]);
      }
    };
    run();
  }, []);

  return (
    
    <main className="content">
      <section className="hero hero--tight">
        <h1>Luxury travel, reimagined.</h1>
        <p>Avante brings private jets, helicopters, and yachts into one seamless experience.</p>
        <div className="hero__cta">
          <Link className="btn btn--primary" href="/private-jet">Explore Private Jets</Link>
          <Link className="btn btn--secondary" href="/helicopter">Helicopter <span className="soon-inline">Coming Soon</span></Link>
          <Link className="btn btn--secondary" href="/yacht">Yacht <span className="soon-inline">Coming Soon</span></Link>
        </div>
      </section>

      <section>
        <h2 className="section-title">Live Empty Legs</h2>
        {flights === null ? (
          <div className="grid"><div className="skeleton-block" /><div className="skeleton-block" /><div className="skeleton-block" /></div>
        ) : flights.length === 0 ? (
          <div className="notice">No flights right now. Check back soon.</div>
        ) : (
          <div className="grid">
            {flights.map((f) => (
              <FlightCard key={f.id} flight={f} />
            ))}
          </div>
        )}

        <div className="center" style={{ marginTop: 16 }}>
          <Link className="btn btn--primary" href="/private-jet">See all Private Jet deals</Link>
        </div>
      </section>
    </main>
  );
}