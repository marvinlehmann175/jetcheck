// components/FlightCard.jsx
"use client";

import React from "react";

function fmtMoney(value, currency) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  try {
    return new Intl.NumberFormat(undefined, { 
      style: "currency", 
      currency: currency || "EUR",   // <-- hier EUR statt USD
      maximumFractionDigits: 0 
    }).format(Number(value));
  } catch {
    return `€${Math.round(Number(value)).toLocaleString()}`;  // Fallback auf Euro
  }
}
function fmtDateLong(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "long", year: "numeric" }).format(new Date(iso));
  } catch { return iso.slice(0,10); }
}
function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  } catch { return iso.slice(11,16); }
}
function minsDiff(a, b) {
  if (!a || !b) return null;
  const d = Math.max(0, (new Date(b) - new Date(a)) / 60000);
  const h = Math.floor(d / 60), m = Math.round(d % 60);
  return `${h}h ${m}m`;
}
function timeAgo(iso) {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.max(1, Math.floor(diff))}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}
function dayChip(departureISO) {
  if (!departureISO) return { label: "Upcoming", cls: "chip chip--upcoming" };
  const dep = new Date(departureISO);
  const now = new Date();
  const d0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const d1 = new Date(d0); d1.setDate(d0.getDate()+1);
  const d2 = new Date(d0); d2.setDate(d0.getDate()+2);
  const depDay = new Date(dep.getFullYear(), dep.getMonth(), dep.getDate());
  if (depDay.getTime() === d0.getTime()) return { label: "Today", cls: "chip chip--today" };
  if (depDay.getTime() === d1.getTime()) return { label: "Tomorrow", cls: "chip chip--tomorrow" };
  if (depDay.getTime() <= d2.getTime()) return { label: "Upcoming", cls: "chip chip--upcoming" };
  return { label: "Upcoming", cls: "chip chip--upcoming" };
}
function statusChip(statusRaw) {
  const s = String(statusRaw || "").toLowerCase();
  let text = "Unknown", dot = "muted";
  if (s.includes("available")) { text = "Available"; dot = "ok"; }
  else if (s.includes("pending")) { text = "Pending"; dot = "warn"; }
  return (
    <span className="chip chip--status">
      <span className={`status-dot dot--${dot}`} />
      {text}
    </span>
  );
}

export default function FlightCard({ flight }) {
  const {
    origin_iata, origin_name, departure_ts,
    destination_iata, destination_name, arrival_ts,
    aircraft, seats, aircraft_seats,
    price_current, price_normal, currency_effective,
    link_latest, status_latest, status,
    last_seen_at
  } = flight || {};

  const depTime = fmtTime(departure_ts);
  const arrTime = fmtTime(arrival_ts);
  const duration = minsDiff(departure_ts, arrival_ts);

  const chip = dayChip(departure_ts);
  const stat = statusChip(status_latest ?? status);

  const aircraftName = (aircraft && String(aircraft).trim()) || "Unknown";
  const seatCount = seats ?? aircraft_seats ?? null;

  const price = price_current ?? price_normal ?? null;
  const currency = currency_effective || "EUR";

  return (
    <article className="card flightcard">
      {/* Row 1: left day chip, right status */}
      <div className="flightcard__toprow">
        <div className="flightcard__chips-left">
          <span className={chip.cls}>{chip.label}</span>
        </div>
        <div className="flightcard__chips">{stat}</div>
      </div>

      {/* Row 2: Titles + Codes with duration divider */}
      <div className="flightcard__airports">
        <div className="flightcard__airport">
          <div className="flightcard__label">Departure</div>
          <div className="flightcard__code">{(origin_iata || "").toUpperCase() || "—"}</div>
          <div className="flightcard__name">{origin_name || origin_iata || "—"}</div>
        </div>

        <div className="flightcard__divider">
          <div className="divider-line" />
          <div className="divider-duration">{duration || "—"}</div>
          <div className="divider-line" />
        </div>

        <div className="flightcard__airport flightcard__airport--right">
          <div className="flightcard__label">Arrival</div>
          <div className="flightcard__code">{(destination_iata || "").toUpperCase() || "—"}</div>
          <div className="flightcard__name">{destination_name || destination_iata || "—"}</div>
        </div>
      </div>

      {/* Dates & times */}
      <div className="flightcard__grid-2">
        <div className="info-block">
          <div className="info-title">Date</div>
          <div className="info-value">{fmtDateLong(departure_ts)}</div>
        </div>
        <div className="info-block">
          <div className="info-title">Time</div>
          <div className="info-value">{depTime} → {arrTime}</div>
        </div>
      </div>

      {/* Glassy meta box (2 cols): Aircraft / Seats */}
      <div className="meta-glass">
        <div className="meta-col">
          <div className="meta-heading">Aircraft</div>
          {aircraftName !== "Unknown" ? (
            <a className="meta-link" href={`#aircraft-${encodeURIComponent(aircraftName)}`}>
              {aircraftName}
            </a>
          ) : (
            <div className="meta-text">Unknown</div>
          )}
        </div>
        <div className="meta-col">
          <div className="meta-heading">Seats</div>
          <div className="meta-text">{seatCount != null ? seatCount : "—"}</div>
        </div>
      </div>

      {/* Price + CTA */}
      <div className="price-cta-row">
        <div className="price-wrap">
          <div className="price-now">{fmtMoney(price, currency)}</div>
        </div>
        <a
          className={link_latest ? "btn--book-cta" : "btn--book-cta btn--disabled"}
          href={link_latest || "#"}
          target="_blank"
          rel="noopener noreferrer"
          aria-disabled={!link_latest}
        >
          <span className="btn-glow" />
          <span className="btn-sheen" />
          View deal
        </a>
      </div>

      {/* Footer: Updated */}
      <div className="card__footer">
        <div className="updated-footnote">Updated {timeAgo(last_seen_at)}</div>
      </div>
    </article>
  );
}