"use client";

export default function FlightCard({ flight }) {
  const { route, date, time, price, link, source, discount, aircraft } = flight || {};

  return (
    <article className="card">
      <div className="card__head">
        <span className="badge">{source || "Unknown"}</span>
        {discount ? <span className="badge badge--deal">-{discount}%</span> : null}
      </div>

      <h3 className="route">{route || "–"}</h3>

      <div className="meta">
        <div>{date || "n/a"}</div>
        <div>{time || ""}</div>
        {aircraft ? <div>{aircraft}</div> : null}
        {price ? <div className="price">{price}</div> : null}
      </div>

      {link ? (
        <a className="btn btn--primary" href={link} target="_blank" rel="noreferrer">
          Buchen / Details
        </a>
      ) : null}
    </article>
  );
}