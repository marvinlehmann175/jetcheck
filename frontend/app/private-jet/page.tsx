"use client";

import { useEffect, useMemo, useState, useLayoutEffect, useRef } from "react";
import FlightCard from "../../components/FlightCard.jsx";
import FiltersDrawer from "../../components/FiltersDrawer.jsx";
import { messages } from "../i18n.js";
import { useI18n } from "@/app/_providers/I18nProvider";

// --- types ---------------------------------------------------------------
type Option = { value: string; label: string };

export type Flight = {
  id: string | number;
  source?: string | null;

  origin_iata?: string | null;
  origin_name?: string | null;
  origin_tz?: string | null;

  destination_iata?: string | null;
  destination_name?: string | null;
  destination_tz?: string | null;

  departure_ts?: string | null; // ISO "2025-08-16T09:12:00Z"
  arrival_ts?: string | null;

  aircraft?: string | null;

  link_latest?: string | null;

  currency_effective?: string | null;
  price_current?: number | null;
  price_normal?: number | null;
  discount_percent?: number | null;

  status?: string | null;
  status_latest?: string | null;
  last_seen_at?: string | null;

  probability?: number | null;
};

// allow indexing messages by string safely
type Dict = Record<string, string>;

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "https://jetcheck.onrender.com";

export default function Home() {
  // --- i18n ---------------------------------------------------------------
  const { t } = useI18n();
  const [lang] = useState("en");
  const dict: Dict = (messages as Record<string, Dict>)[lang] || {};
  const tt = (k: string, fb: string) => dict[k] ?? fb;

  // --- data + ui state ----------------------------------------------------
  const [flights, setFlights] = useState<Flight[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  // Filters
  const [status, setStatus] = useState<string>(""); // "", "available", "pending"
  const [from, setFrom] = useState<string>(""); // IATA
  const [to, setTo] = useState<string>(""); // IATA
  const [date, setDate] = useState<string>(""); // YYYY-MM-DD
  const [maxPrice, setMaxPrice] = useState<string>("");
  const [aircraft, setAircraft] = useState<string>("");

  // Sort/pagination
  const [sortKey, setSortKey] = useState<"departure" | "price" | "seen">(
    "departure"
  );
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState<number>(1);
  const pageSize = 12;

  // Drawer
  const [showFilters, setShowFilters] = useState<boolean>(false);

  // --- floating controls (below the floating nav) ---------------------------
  const TOPBAR_H = 72; // sync with your .topbar-spacer / nav height
  const [floating, setFloating] = useState(false);
  const [barH, setBarH] = useState(0);
  const barRef = useRef<HTMLElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // measure bar height for placeholder to prevent layout jump
  useLayoutEffect(() => {
    const measure = () => {
      if (barRef.current) setBarH(barRef.current.offsetHeight);
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (barRef.current) ro.observe(barRef.current);
    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
      ro.disconnect();
    };
  }, []);

  // --- fetch --------------------------------------------------------------
  // fetch flights once on mount
  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setError("");
      setLoading(true);
      try {
        const url = `${API_BASE}/api/flights?page_size=200&sort_key=departure_ts&sort_dir=asc`;
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!cancelled) {
          setFlights(Array.isArray(data) ? (data as Flight[]) : []);
        }
      } catch (e) {
        if (!cancelled) {
          setError("Failed to load flights");
          setFlights([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- helpers ------------------------------------------------------------
  // Always hide 'unavailable'
  const baseFlights = useMemo(() => {
    return (flights || []).filter((f: Flight) => {
      const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
      return s !== "unavailable";
    });
  }, [flights]);

  const priceToNumber = (pCurrent: unknown, pNormal: unknown) => {
    const val =
      typeof pCurrent === "number"
        ? pCurrent
        : typeof pNormal === "number"
        ? pNormal
        : NaN;
    return Number.isFinite(val) ? (val as number) : Number.POSITIVE_INFINITY;
  };

  // Options for dropdowns (filtered to “currently possible”)
  const departureOptions = useMemo<Option[]>(() => {
    const m = new Map<string, string>();
    for (const f of baseFlights as Flight[]) {
      const code = (f.origin_iata || "").toUpperCase();
      if (!code) continue;
      if (to && (f.destination_iata || "").toUpperCase() !== to.toUpperCase())
        continue;
      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) continue;
      }
      const name = f.origin_name || code;
      if (!m.has(code)) m.set(code, `${code} — ${name}`);
    }
    const arr: Option[] = Array.from(m.entries()).map(([value, label]) => ({
      value,
      label,
    }));
    return arr.sort((a, b) => a.label.localeCompare(b.label));
  }, [baseFlights, status, to]);

  const destinationOptions = useMemo<Option[]>(() => {
    const m = new Map<string, string>();
    for (const f of baseFlights as Flight[]) {
      const code = (f.destination_iata || "").toUpperCase();
      if (!code) continue;
      if (from && (f.origin_iata || "").toUpperCase() !== from.toUpperCase())
        continue;
      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) continue;
      }
      const name = f.destination_name || code;
      if (!m.has(code)) m.set(code, `${code} — ${name}`);
    }
    const arr: Option[] = Array.from(m.entries()).map(([value, label]) => ({
      value,
      label,
    }));
    return arr.sort((a, b) => a.label.localeCompare(b.label));
  }, [baseFlights, status, from]);

  const aircraftOptions = useMemo<string[]>(() => {
    const set = new Set<string>();
    for (const f of baseFlights as Flight[]) {
      if (f.aircraft && String(f.aircraft).trim())
        set.add(String(f.aircraft).trim());
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [baseFlights]);

  // Active filters counter (for the Filter button)
  const activeFilters = useMemo(() => {
    let n = 0;
    if (status.trim()) n++;
    if (from.trim()) n++;
    if (to.trim()) n++;
    if (date.trim()) n++;
    if (String(maxPrice).trim()) n++;
    if (aircraft.trim()) n++;
    return n;
  }, [status, from, to, date, maxPrice, aircraft]);

  const resetFilters = () => {
    setStatus("");
    setFrom("");
    setTo("");
    setDate("");
    setMaxPrice("");
    setAircraft("");
  };

  // --- filtering/sorting/paging ------------------------------------------
  const filtered = useMemo(() => {
    return (baseFlights as Flight[]).filter((f: Flight) => {
      const depMs = f.departure_ts ? new Date(f.departure_ts).getTime() : 0;
      if (depMs && depMs < Date.now()) return false;

      if (status) {
        const s = String(f.status_latest ?? f.status ?? "").toLowerCase();
        if (s !== status.toLowerCase()) return false;
      }

      if (from && (f.origin_iata || "").toUpperCase() !== from.toUpperCase())
        return false;
      if (to && (f.destination_iata || "").toUpperCase() !== to.toUpperCase())
        return false;

      if (date) {
        const depDate = (f.departure_ts || "").slice(0, 10);
        if (depDate !== date) return false;
      }

      if (maxPrice) {
        const max = Number(maxPrice);
        if (!Number.isNaN(max)) {
          const p = priceToNumber(f.price_current, f.price_normal);
          if (p > max) return false;
        }
      }

      if (aircraft && String(f.aircraft || "") !== aircraft) return false;

      return true;
    });
  }, [baseFlights, status, from, to, date, maxPrice, aircraft]);

  const sorted = useMemo<Flight[]>(() => {
    const arr = [...(filtered as Flight[])];
    arr.sort((a, b) => {
      let A: string | number, B: string | number;
      switch (sortKey) {
        case "price":
          A = priceToNumber(a.price_current, a.price_normal);
          B = priceToNumber(b.price_current, b.price_normal);
          break;
        case "seen":
          A = a.last_seen_at || "";
          B = b.last_seen_at || "";
          break;
        case "departure":
        default:
          A = a.departure_ts || "";
          B = b.departure_ts || "";
          break;
      }
      if (A < B) return sortDir === "asc" ? -1 : 1;
      if (A > B) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, currentPage]);

  useEffect(() => {
    setPage(1);
  }, [status, from, to, date, maxPrice, aircraft, sortKey, sortDir]);

  // --- render -------------------------------------------------------------
  return (
    <main className="screen">
      <section className="hero">
        <h1>{t("hero.title", "Exclusive Empty Legs in Real Time")}</h1>
        <p>
          {t("hero.subtitle", "Find available empty legs with just one click.")}
        </p>
      </section>

      {/* Controls: transparent shell, left filter, right sorts */}
      <section className="controls-bar">
        <div className="controls-bar__shell">
          <div className="controls-left">
            <button
              className="pill pill--action"
              onClick={() => setShowFilters(true)}
              aria-expanded={showFilters ? "true" : "false"}
              aria-controls="filters-drawer"
            >
              {t("filters.button", "Filter")}
              {activeFilters > 0 ? ` (${activeFilters})` : ""}
            </button>
          </div>

          <div className="controls-right">
            <select
              className="pill pill--select"
              value={sortKey}
              onChange={(e) =>
                setSortKey(e.target.value as "departure" | "price" | "seen")
              }
              aria-label={t("sort.label", "Sort by")}
            >
              <option value="departure">
                {t("sort.departure", "Departure Time")}
              </option>
              <option value="price">{t("sort.price", "Price")}</option>
              <option value="seen">{t("sort.seen", "Last Seen")}</option>
            </select>

            <select
              className="pill pill--select"
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value as "asc" | "desc")}
              aria-label={t("sort.direction", "Sort direction")}
            >
              <option value="asc">{t("sort.asc", "Ascending")}</option>
              <option value="desc">{t("sort.desc", "Descending")}</option>
            </select>
          </div>
        </div>
      </section>

      {/* Drawer */}
      <FiltersDrawer
        open={showFilters}
        onClose={() => setShowFilters(false)}
        t={tt}
        // values
        status={status}
        from={from}
        to={to}
        date={date}
        maxPrice={maxPrice}
        aircraft={aircraft}
        // setters
        setStatus={setStatus}
        setFrom={setFrom}
        setTo={setTo}
        setDate={setDate}
        setMaxPrice={setMaxPrice}
        setAircraft={setAircraft}
        resetFilters={resetFilters}
        // options
        departureOptions={departureOptions}
        destinationOptions={destinationOptions}
        aircraftOptions={aircraftOptions}
      />

      <section className="content">
        {loading && (
          <div
            className="grid"
            role="status"
            aria-live="polite"
            aria-busy="true"
          >
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} className="card skeleton-block" />
            ))}
          </div>
        )}

        {!loading && error && (
          <div
            className="notice notice--error"
            role="alert"
            aria-live="assertive"
          >
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {sorted.length === 0 ? (
              <div className="notice" role="status" aria-live="polite">
                {t(
                  "emptyState",
                  "No flights for the current filters. Try changing the date or increasing the max price."
                )}
              </div>
            ) : (
              <>
                <div className="grid">
                  {pageItems.map((f: Flight) => (
                    <FlightCard key={String(f.id)} flight={f} />
                  ))}
                </div>

                <div className="pager">
                  <button
                    className="btn"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    ◀︎ {t("pager.back", "Back")}
                  </button>
                  <div className="pager__info">
                    {t("pager.page", "Page")} {currentPage} / {totalPages} ·{" "}
                    {total} {t("pager.results", "results")}
                  </div>
                  <button
                    className="btn"
                    disabled={currentPage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    {t("pager.next", "Next")} ▶︎
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </section>
    </main>
  );
}
