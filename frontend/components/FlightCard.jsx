"use client";

import LocalTime from '@/components/LocalTime';
import { parsePgTimestamptz, dayLabel, formatLocalDate } from '@/utils/time';

function fmtPrice(amount, currency = "EUR") {
  if (amount == null) return null;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(Number(amount));
  } catch {
    return `${amount} ${currency}`;
  }
}

function timeAgo(ts) {
  if (!ts) return null;
  const diffMs = Date.now() - parsePgTimestamptz(ts).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "now";
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} h ago`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD} d ago`;
}

export default function FlightCard({ flight }) {
  if (!flight) return null;

  const {
    source,
    origin_iata, origin_name, origin_tz,
    destination_iata, destination_name, destination_tz,
    departure_ts, arrival_ts,
    link_latest,
    price_current,
    price_normal,
    discount_percent,
    status_latest,
    last_seen_at,
  } = flight;

  const oCode = (origin_iata || "—").toUpperCase();
  const dCode = (destination_iata || "—").toUpperCase();
  const oName = origin_name || oCode;
  const dName = destination_name || dCode;

  const priceLabel = fmtPrice(price_current, "EUR");
  const normalPriceLabel = price_normal != null ? fmtPrice(price_normal, "EUR") : null;

  const dayChip = `${dayLabel(departure_ts, origin_tz)} · ${formatLocalDate(departure_ts, origin_tz)}`;

  const showDiscount =
    discount_percent != null && !Number.isNaN(Number(discount_percent));

  const statusText =
    status_latest?.toLowerCase() === "pending" ? "Pending" : status_latest || "";

  return (
    <article className="card flightcard">
      {/* Top row */}
      <div className="flightcard__toprow">
        <div className="chip chip--date">{dayChip}</div>
        {statusText && (
          <div className={`chip chip--status status-chip status-chip--${String(status_latest || "").toLowerCase()}`}>
            {statusText}
          </div>
        )}
      </div>

      {/* Airports & times */}
      <div className="flightcard__airports">
        <div className="flightcard__airport">
          <div className="flightcard__name">{oName}</div>
          <div className="flightcard__code">{oCode}</div>
          <LocalTime ts={departure_ts} tz={origin_tz} stacked className="flightcard__dt" />
        </div>

        <div className="flightcard__arrow" aria-hidden>—</div>

        <div className="flightcard__airport flightcard__airport--right">
          <div className="flightcard__name">{dName}</div>
          <div className="flightcard__code">{dCode}</div>
          <LocalTime ts={arrival_ts} tz={destination_tz || origin_tz} stacked className="flightcard__dt" />
        </div>
      </div>

      {/* Price / CTA or Pending */}
      {priceLabel ? (
        <div className="info-box">
          <div className="info-main">
            <div className="info-title">{priceLabel}</div>
            {(normalPriceLabel || showDiscount) && (
              <div className="info-sub">
                {normalPriceLabel && (
                  <span className="info-label">
                    <span className="info-compare">{normalPriceLabel}</span>
                  </span>
                )}
                {showDiscount && (
                  <span className="info-badge">−{Math.round(discount_percent)}%</span>
                )}
              </div>
            )}
          </div>

          {link_latest && (
            <a
              className="btn btn--book btn--book-inline"
              href={link_latest}
              target="_blank"
              rel="noreferrer"
              aria-label={`Book flight ${oCode} to ${dCode}`}
            >
              ✈ Book now
            </a>
          )}
        </div>
      ) : (
        <div className="info-box info-box--stack">
          <div className="info-title">Flight not confirmed yet</div>
          {Number.isFinite(flight?.probability) && (
            <div className="info-sub">
              <span className="info-label">Probability</span>
              <span className="info-badge info-badge--prob">
                ~{Math.round(Number(flight.probability) * 100)}%
              </span>
            </div>
          )}
        </div>
      )}

      <div className="card__meta">
        <div className="meta-left">
          <span className={`opby-text opby--${(source || "").toLowerCase()}`}>
            Operated by <strong>{source || "—"}</strong>
          </span>
        </div>
        <div className="meta-right">
          {last_seen_at && (
            <span className="meta-updated">updated {timeAgo(last_seen_at)}</span>
          )}
        </div>
      </div>
    </article>
  );
}