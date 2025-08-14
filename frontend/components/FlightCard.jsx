"use client";

function fmtDate(ts) {
  if (!ts) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(ts));
  } catch {
    return "—";
  }
}

function fmtTime(ts) {
  if (!ts) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(ts));
  } catch {
    return "—";
  }
}

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
  const diffMs = Date.now() - new Date(ts).getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "now";
  if (diffMin < 60) return `${diffMin} Min ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `vor ${diffH} Std`;
  const diffD = Math.floor(diffH / 24);
  return `vor ${diffD} Tg`;
}

export default function FlightCard({ flight }) {
  if (!flight) return null;

  const {
    source,
    origin_iata,
    origin_name,
    destination_iata,
    destination_name,
    departure_ts,
    arrival_ts,
    aircraft,
    link_latest,
    currency_effective,
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

  const depDate = fmtDate(departure_ts);
  const depTime = fmtTime(departure_ts);
  const arrTime = fmtTime(arrival_ts);

  const priceLabel = fmtPrice(price_current, currency_effective);
  const normalPriceLabel =
    price_normal != null ? fmtPrice(price_normal, currency_effective) : null;

  const showDiscount =
    discount_percent != null && !Number.isNaN(Number(discount_percent));

  const statusText =
    status_latest?.toLowerCase() === "pending"
      ? "Pending"
      : status_latest || "";

  return (
    <article className="card flightcard">
      {/* Kopfzeile */}
      <div className="flightcard__toprow">
        <div className="chip chip--date">{depDate}</div>
        {statusText && (
          <div
            className={`chip chip--status status-chip status-chip--${String(
              status_latest || ""
            ).toLowerCase()}`}
          >
            {statusText}
          </div>
        )}
      </div>

      {/* Airports & Zeiten */}
      <div className="flightcard__airports">
        <div className="flightcard__airport">
          <div className="flightcard__name">{oName}</div>
          <div className="flightcard__code">{oCode}</div>
          <div className="flightcard__time">{depTime}</div>
        </div>
        <div className="flightcard__arrow" aria-hidden>
          —
        </div>
        <div className="flightcard__airport flightcard__airport--right">
          <div className="flightcard__name">{dName}</div>
          <div className="flightcard__code">{dCode}</div>
          <div className="flightcard__time">{arrTime}</div>
        </div>
      </div>

      {/* Preis / CTA / Extras */}
      {/* Preis / CTA ODER Pending — immer mit gleicher Box-Optik */}
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
                  <span className="info-badge">
                    −{Math.round(discount_percent)}%
                  </span>
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

      {aircraft && <div className="aircraft">{aircraft}</div>}

      {/* Meta unter dem Footer */}
      <div className="card__meta">
        <div className="meta-left">
          <span className={`opby-text opby--${(source || "").toLowerCase()}`}>
            Operated by <strong>{source || "—"}</strong>
          </span>
        </div>
        <div className="meta-right">
          {last_seen_at && (
            <span className="meta-updated">
              updated {timeAgo(last_seen_at)}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
