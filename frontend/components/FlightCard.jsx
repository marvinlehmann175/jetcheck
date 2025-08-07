"use client";
import React from "react";

export default function FlightCard({ flight }) {
  const { route, date, time, price, link, source } = flight;

  const [dep, arr] = (route || "").split("→").map((s) => s?.trim());
  const prettyPrice = price || "—";

  return (
    <article className="card">
      {source && <div className={`source-badge source-${source.toLowerCase()}`}>{source}</div>}

      <div className="card__row">
        <div className="chip chip--from" title={dep}>{dep || "—"}</div>
        <div className="arrow">→</div>
        <div className="chip chip--to" title={arr}>{arr || "—"}</div>
      </div>

      <div className="card__meta">
        <div className="meta">
          <span className="meta__label">Datum</span>
          <span className="meta__value">{date || "—"}</span>
        </div>
        <div className="meta">
          <span className="meta__label">Zeit</span>
          <span className="meta__value">{time || "—"}</span>
        </div>
        <div className="meta">
          <span className="meta__label">Preis</span>
          <span className="meta__value">{prettyPrice}</span>
        </div>
      </div>

      <div className="card__cta">
        {link ? (
          <a className="btn btn--primary" href={link} target="_blank" rel="noopener noreferrer">
            Buchen
          </a>
        ) : (
          <button className="btn btn--disabled" disabled>Details</button>
        )}
      </div>
    </article>
  );
}