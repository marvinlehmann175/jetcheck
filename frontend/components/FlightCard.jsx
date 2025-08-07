"use client";

function parseRoute(route = "") {
  const [fromRaw = "", toRaw = ""] = route.split("→");
  return { from: fromRaw.trim(), to: toRaw.trim() };
}

function parseTimes(time = "") {
  // akzeptiert "06:40 – 09:00" | "06:40-09:00" | "06:40 — 09:00"
  const t = time.replace(/—/g, "–").replace(/-/g, "–");
  const [dep = "", arr = ""] = t.split("–").map(s => s.trim());
  return { dep, arr };
}

export default function FlightCard({ flight }) {
  const {
    route, date, time, price, link, source, discount, aircraft,
    originalPrice, // optional: wenn vorhanden, zeigen wir Streichpreis & Ersparnis
  } = flight || {};

  const { from, to } = parseRoute(route);
  const { dep, arr } = parseTimes(time);

  // Preislogik
  const hasPrice = !!price;
  const base = typeof originalPrice === "number" ? originalPrice : null;
  const current = typeof price === "number" ? price : null;
  const saved = base && current ? Math.max(0, base - current) : null;

  return (
    <article className="card flightcard">
      {/* Kopf: Datum oben rechts */}
      <header className="flightcard__head">
        <div className="flightcard__date">{date || "–"}</div>
      </header>

      {/* Strecke */}
      <div className="flightcard__route">
        <div className="flightcard__col">
          <div className="flightcard__airport">{from || "—"}</div>
          <div className="flightcard__time">{dep || ""}</div>
        </div>

        <div className="flightcard__dash">
          <span className="flightcard__line" />
        </div>

        <div className="flightcard__col flightcard__col--right">
          <div className="flightcard__airport">{to || "—"}</div>
          <div className="flightcard__time">{arr || ""}</div>
        </div>
      </div>

      {/* Aircraft (klein, optional) */}
      {aircraft ? <div className="flightcard__aircraft">{aircraft}</div> : null}

      {/* Preisbereich */}
      <div className="flightcard__priceRow">
        {hasPrice ? (
          <>
            {base && base > (current ?? 0) ? (
              <div className="flightcard__priceGroup">
                <div className="price price--current">
                  {new Intl.NumberFormat("de-DE").format(current)} €
                </div>
                <div className="price price--strike">
                  {new Intl.NumberFormat("de-DE").format(base)} €
                </div>
                {saved ? (
                  <div className="price price--saved">−{new Intl.NumberFormat("de-DE").format(saved)} €</div>
                ) : null}
              </div>
            ) : (
              <div className="price price--current">
                {typeof price === "number"
                  ? `${new Intl.NumberFormat("de-DE").format(price)} €`
                  : price}
              </div>
            )}
          </>
        ) : (
          <div className="price price--pending">Not confirmed</div>
        )}
      </div>

      {/* CTA + Operated by */}
      <div className="flightcard__footer">
        {link ? (
          <a className="btn btn--primary" href={link} target="_blank" rel="noreferrer">
            Details / Buchen
          </a>
        ) : (
          <button className="btn btn--disabled" disabled>Details</button>
        )}

        <div className={`opby ${source?.toLowerCase() === "globeair" ? "opby--globeair" : source?.toLowerCase() === "asl" ? "opby--asl" : ""}`}>
          Operated by {source || "—"}
        </div>
      </div>
    </article>
  );
}