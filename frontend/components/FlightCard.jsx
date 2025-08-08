"use client";

const airportNames = {
  'IBZ': 'Ibiza',
  'ZRH': 'Zürich',
  'AMS': 'Amsterdam',
  'FRA': 'Frankfurt',
  'LHR': 'London Heathrow',
  // weitere Codes nach Bedarf
};

function splitRoute(route = "") {
  // akzeptiert "IBZ → ZRH" oder "Ibiza → Zürich"
  const parts = route.split(/→|->|-/).map(s => s.trim());
  const [fromRaw = "", toRaw = ""] = parts;
  const code = s => (s.match(/^[A-Za-z]{3}$/) ? s.toUpperCase() : null);

  return {
    from_code: code(fromRaw) || fromRaw.slice(0,3).toUpperCase(),
    to_code: code(toRaw) || toRaw.slice(0,3).toUpperCase(),
    // Wenn du echte Namen im Datensatz hast, nutzt du die:
    // from_name/to_name; sonst fallback auf code
    from_name: null,
    to_name: null,
  };
}

function splitTimes(time = "", dep_time, arr_time) {
  if (dep_time || arr_time) return { dep: dep_time || "", arr: arr_time || "" };
  // versucht "08:30 – 10:05", "08:30-10:05" zu parsen
  const m = time.match(/(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})/);
  return m ? { dep: m[1], arr: m[2] } : { dep: time || "", arr: "" };
}

export default function FlightCard({ flight }) {
  const {
    route, date, time, price, link, source, discount, aircraft,
    // optionale exakt strukturierte Felder, falls vorhanden:
    from_code, to_code, from_name, to_name, dep_time, arr_time, confirmed
  } = flight || {};

  const r = splitRoute(route);
  const codes = {
    from: from_code || r.from_code,
    to: to_code || r.to_code,
  };
  const names = {
    from: airportNames[codes.from] || from_name || r.from_name || codes.from,
    to: airportNames[codes.to] || to_name || r.to_name || codes.to,
  };
  const t = splitTimes(time, dep_time, arr_time);

  const notConfirmed = confirmed === false || /not.*confirm/i.test(String(price || ""));

  return (
    <article className="card flightcard">
      {/* Kopfzeile */}
      <div className="flightcard__toprow">
        <div className="flightcard__date">{date || "—"}</div>
      </div>

      {/* Airports & Zeiten */}
      <div className="flightcard__airports">
        <div className="flightcard__airport">
          <div className="flightcard__name">{names.from}</div>
          <div className="flightcard__code">{codes.from}</div>
          <div className="flightcard__time">{t.dep || "—"}</div>
        </div>

        <div className="flightcard__arrow" aria-hidden>—</div>

        <div className="flightcard__airport flightcard__airport--right">
          <div className="flightcard__name">{names.to}</div>
          <div className="flightcard__code">{codes.to}</div>
          <div className="flightcard__time">{t.arr || "—"}</div>
        </div>
      </div>

      {/* Preis & Status */}
      <div className="flightcard__pricing">
        {price ? (
          <div className="price">{price}</div>
        ) : (
          <div className="status-note">Flight not yet confirmed</div>
        )}
        {discount ? (
          <div className="badge badge--deal">−{discount}%</div>
        ) : null}
        {aircraft ? <div className="aircraft">{aircraft}</div> : null}
      </div>

      {/* Footer fixiert am Kartenende */}
      <div className="card__footer">
        {source ? (
          <span className="opby">
            Operated by <strong>{source}</strong>
          </span>
        ) : (
          <span className="opby">Operated by <strong>—</strong></span>
        )}

        {link ? (
          <a className="btn btn--primary" href={link} target="_blank" rel="noreferrer">
            Details / Buchen
          </a>
        ) : (
          <button className="btn btn--disabled" disabled>Details</button>
        )}
      </div>
    </article>
  );
}