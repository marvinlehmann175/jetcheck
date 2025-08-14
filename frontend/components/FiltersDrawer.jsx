"use client";

export default function FiltersDrawer({
  open,
  onClose,
  t,
  // values
  status,
  from,
  to,
  date,
  maxPrice,
  aircraft,
  // setters
  setStatus,
  setFrom,
  setTo,
  setDate,
  setMaxPrice,
  setAircraft,
  resetFilters,
  // options
  departureOptions,
  destinationOptions,
  aircraftOptions,
}) {
  const handleSubmit = (e) => {
    e.preventDefault();
    onClose?.();
  };

  return (
    <>
      {open && (
        <div
          className="filters-overlay"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        id="filters-drawer"
        className={`filters-drawer ${open ? "open" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="filters-title"
      >
        <div className="filters-header">
          <h2 id="filters-title">{t("filters.title", "Filters")}</h2>
          <button
            className="btn btn-close"
            onClick={onClose}
            aria-label={t("filters.close", "Close")}
          >
            ✕
          </button>
        </div>

        <form className="filters-form" onSubmit={handleSubmit}>
          {/* Status */}
          <label className="label">
            {t("filters.status", "Status")}
            <select
              className="select"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">{t("filters.all", "All")}</option>
              <option value="available">{t("status.available", "Available")}</option>
              <option value="pending">{t("status.pending", "Pending")}</option>
            </select>
          </label>

          {/* Departure + Destination side-by-side */}
          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr" }}>
            <label className="label">
              {t("filters.departure", "Departure (City/IATA)")}
              <select
                className="select"
                value={from}
                onChange={(e) => {
                  const value = e.target.value;
                  setFrom(value);
                  // keep destination only if still reachable
                  if (value && to) {
                    const stillValid = destinationOptions.some((o) => o.value === to);
                    if (!stillValid) setTo("");
                  }
                }}
              >
                <option value="">{t("filters.any", "Any")}</option>
                {departureOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="label">
              {t("filters.destination", "Destination (City/IATA)")}
              <select
                className="select"
                value={to}
                onChange={(e) => {
                  const value = e.target.value;
                  setTo(value);
                  // keep departure only if still valid
                  if (value && from) {
                    const stillValid = departureOptions.some((o) => o.value === from);
                    if (!stillValid) setFrom("");
                  }
                }}
              >
                <option value="">{t("filters.any", "Any")}</option>
                {destinationOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* Date */}
          <label className="label">
            {t("filters.date", "Date")}
            <input
              className="input"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>

          {/* Max price */}
          <label className="label">
            {t("filters.maxPrice", "Max Price (€)")}
            <input
              className="input"
              type="number"
              inputMode="numeric"
              placeholder="15000"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </label>

          {/* Aircraft */}
          <label className="label">
            {t("filters.aircraft", "Aircraft type")}
            <select
              className="select"
              value={aircraft}
              onChange={(e) => setAircraft(e.target.value)}
            >
              <option value="">{t("filters.any", "Any")}</option>
              {aircraftOptions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>

          <div className="filters-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={resetFilters}
            >
              {t("filters.reset", "Reset")}
            </button>
            <button type="submit" className="btn btn-primary">
              {t("filters.apply", "Apply")}
            </button>
          </div>
        </form>
      </aside>
    </>
  );
}