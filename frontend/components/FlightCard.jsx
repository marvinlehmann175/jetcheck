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
  if (diffMin < 1) return "gerade eben";
  if (diffMin < 60) return `vor ${diffMin} Min`;
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
      ? "Flight not yet confirmed"
      : status_latest || "";

  return (
    <article className="card flightcard">
      {/* Kopfzeile */}
      <div className="flightcard__toprow">
        <div className="flightcard__date">{depDate}</div>
        {statusText && (
          <div
            className={`status-chip status-chip--${String(
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

      {/* Preis & Status */}
      <div className="flightcard__pricing">
        {priceLabel ? (
          <div className="price">
            {priceLabel}
            {normalPriceLabel && (
              <span className="price--strike">{normalPriceLabel}</span>
            )}
          </div>
        ) : (
          <div className="status-note">{statusText}</div>
        )}
        {showDiscount && (
          <div className="badge badge--deal">
            −{Math.round(discount_percent)}%
          </div>
        )}
        {aircraft && <div className="aircraft">{aircraft}</div>}
      </div>

      {/* Footer */}
      <div className="card__footer">
        {link_latest ? (
          <a
            className="btn btn--book"
            href={link_latest}
            target="_blank"
            rel="noreferrer"
          >
            ✈ Jetzt buchen
          </a>
        ) : (
          <button className="btn btn--disabled" disabled>
            Details
          </button>
        )}

        <span className={`opby opby--${(source || "").toLowerCase()}`}>
          <span>
            Operated by <strong>{source || "—"}</strong>
          </span>
          {last_seen_at && (
            <span className="opby__updated">
              updated {timeAgo(last_seen_at)}
            </span>
          )}
        </span>
      </div>
    </article>
  );
}
