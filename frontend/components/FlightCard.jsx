"use client";

import Link from "next/link";

function fmtMoney(n, currency = "USD") {
  if (typeof n !== "number" || Number.isNaN(n)) return null;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(n);
  } catch {
    return `${Math.round(n).toLocaleString()} ${currency}`;
  }
}

function timeAgo(iso) {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.round(hr / 24);
  return `${d}d ago`;
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function parts(iso) {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  const DD = String(d.getDate()).padStart(2, "0");
  const MMMM = MONTHS[d.getMonth()];
  const YYYY = d.getFullYear();
  return {
    date: `${DD}. ${MMMM} ${YYYY}`,
    time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  };
}

function dayChip(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const dd = new Date(d);
  dd.setHours(0, 0, 0, 0);
  const diff = Math.round((dd.getTime() - today.getTime()) / 86400000);
  if (diff === 0) return <span className="chip chip--today">Today</span>;
  if (diff === 1) return <span className="chip chip--tomorrow">Tomorrow</span>;
  return null;
}

export default function FlightCard({ flight }) {
  const {
    id,
    origin_iata,
    origin_name,
    destination_iata,
    destination_name,
    departure_ts,
    arrival_ts,
    aircraft,
    price_current,
    price_normal,
    currency_effective,
    status_latest,
    status,
    last_seen_at,
    link_latest,
  } = flight || {};

  const statusVal = String(status_latest ?? status ?? "").toLowerCase();
  const statusText =
    statusVal === "available"
      ? "Available"
      : statusVal === "pending"
      ? "Pending"
      : statusVal
      ? statusVal.charAt(0).toUpperCase() + statusVal.slice(1)
      : "Status";

  const dotClass =
    statusVal === "available"
      ? "dot--ok"
      : statusVal === "pending"
      ? "dot--warn"
      : "dot--muted";

  const dep = parts(departure_ts);
  const arr = parts(arrival_ts);

  const currentPrice = fmtMoney(
    typeof price_current === "number"
      ? price_current
      : typeof price_normal === "number"
      ? price_normal
      : NaN,
    currency_effective || "USD"
  );

  const hasAircraft = !!(aircraft && String(aircraft).trim());
  const aircraftHref = hasAircraft
    ? `/aircraft/${encodeURIComponent(aircraft)}`
    : null;

  return (
    <div className="card flightcard" data-id={id}>
      {/* Top chips (left-aligned): Today/Tomorrow + Status */}
      <div className="flightcard__toprow">
        <div className="flightcard__chips">
          {dayChip(departure_ts)}
          <span className="chip chip--status">
            <span className={`status-dot ${dotClass}`} />
            {statusText}
          </span>
        </div>
        <div />
      </div>

      {/* Airports */}
      <div className="flightcard__airports">
        <div className="flightcard__airport">
          <span className="flightcard__label">Departure</span>
          <div className="flightcard__code">
            {(origin_iata || "").toUpperCase()}
          </div>
          <div className="flightcard__name">
            {origin_name || origin_iata || "—"}
          </div>
          <div className="flightcard__dt flightcard__dt--stack">
            <span className="flightcard__date">{dep.date}</span>
            <span className="flightcard__time">{dep.time}</span>
          </div>
        </div>

        <div className="flightcard__arrow">→</div>

        <div className="flightcard__airport flightcard__airport--right">
          <span className="flightcard__label">Arrival</span>
          <div className="flightcard__code">
            {(destination_iata || "").toUpperCase()}
          </div>
          <div className="flightcard__name">
            {destination_name || destination_iata || "—"}
          </div>
          <div className="flightcard__dt flightcard__dt--stack">
            <span className="flightcard__date">{arr.date}</span>
            <span className="flightcard__time">{arr.time}</span>
          </div>
        </div>
      </div>

      <div className="info-row">
        {/* Row 1: Aircraft */}
        <div className="info-row__line">
          <div className="info-cell--aircraft">Aircraft</div>
          <div className="info-cell--aircraft-name">
            {flight?.aircraft ? <a href="#">{flight.aircraft}</a> : "Unknown"}
          </div>
        </div>

        {/* Row 2: Price + CTA */}
        <div className="info-row__line">
          <div className="info-cell--price">
            {flight?.price_current
              ? `€ ${flight.price_current.toLocaleString()}`
              : "—"}
          </div>
          <div className="info-cell--cta">
            <button className="btn--book-cta">
              Book
              <span className="btn-sheen"></span>
              <span className="btn-glow"></span>
            </button>
          </div>
        </div>
      </div>

      {/* Footer with updated-ago */}
      <div className="card__footer">
        <div className="updated-footnote">
          {timeAgo(last_seen_at) ? `Updated ${timeAgo(last_seen_at)}` : ""}
        </div>
      </div>
    </div>
  );
}
