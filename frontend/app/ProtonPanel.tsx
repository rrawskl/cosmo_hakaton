"use client";
import { useEffect, useState } from "react";
import { stamp, time } from "../lib/format";
export type ProtonData = {
  status: string;
  range: string;
  observed_at: string | null;
  fetched_at: string | null;
  message: string;
  source: {
    provider: string;
    platform: string;
    role: string;
    endpoint: string | null;
  };
  noaa_scale: { level: string | null };
  internal_status: string;
  trend: string;
  warning_100mev: boolean | null;
  freshness: { age_seconds: number | null; stale: boolean };
  reasons: string[];
  channels: Record<
    string,
    {
      flux: number | null;
      unit: string;
      observed_at: string | null;
      satellite: number | null;
      is_stale: boolean;
      trend: string;
      peak: { flux: number; time: string } | null;
      series: { time: string; flux: number; satellite: number }[];
    }
  >;
};
const names: Record<string, string> = {
  OK: "Актуальные данные",
  DATA_STALE: "Данные устарели",
  DATA_UNAVAILABLE: "Данные недоступны",
  RISING: "↑ Растущий",
  FALLING: "↓ Снижающийся",
  STABLE: "→ Стабильный",
  UNAVAILABLE: "Недостаточно измерений",
};
const energies = [10, 50, 100];
const colors = ["#66d9f1", "#b895ff", "#ffbc69"];
export default function ProtonPanel({
  snapshot,
  historical = false,
}: {
  snapshot?: ProtonData | null;
  historical?: boolean;
}) {
  const [data, setData] = useState<ProtonData | null>(snapshot || null);
  const [range, setRange] = useState("6h");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [enabled, setEnabled] = useState([true, true, true]);
  const [cursor, setCursor] = useState(100);
  useEffect(() => {
    if (snapshot || historical) {
      setData(snapshot || null);
      return;
    }
    const abort = new AbortController();
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const r = await fetch(`/api/protons/history?range=${range}`, {
          signal: abort.signal,
        });
        if (!r.ok) throw Error();
        const d = await r.json();
        if (active) setData(d);
      } catch (e) {
        if (active && !abort.signal.aborted)
          setError("Не удалось связаться с API. Повторите обновление.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 120000);
    return () => {
      active = false;
      abort.abort();
      clearInterval(timer);
    };
  }, [range, refresh, snapshot, historical]);
  const rows = energies.map((e) => data?.channels[`gte_${e}_mev`]);
  const times = rows.flatMap(
    (r) => r?.series.map((p) => Date.parse(p.time)) || [],
  );
  const begin = times.length ? Math.min(...times) : 0,
    end = times.length ? Math.max(...times) : 1;
  const cursorTime = begin + ((end - begin) * cursor) / 100;
  const x = (t: number) => 60 + (700 * (t - begin)) / Math.max(1, end - begin);
  const y = (v: number) =>
    240 - (220 * (Math.log10(Math.max(0.001, v)) + 3)) / 8;
  return (
    <section className="panel protonpanel" aria-label="Протонная обстановка">
      <div className="paneltitle">
        <span>ПРОТОННАЯ ОБСТАНОВКА · NOAA GOES</span>
        <small>Integral Proton Flux</small>
      </div>
      <p className="protonnote">
        Показатель основан на измерениях спутников GOES и характеризует
        солнечно-протонную обстановку в околоземном пространстве. Он не является
        прямым измерением индивидуальной дозы космонавта.
      </p>
      {historical && !snapshot ? (
        <p role="status">
          DATA_UNAVAILABLE — архив протонных измерений для выбранной
          исторической даты не подключён.
        </p>
      ) : (
        <>
          <div className="protoncontrols">
            <label>
              Период графика{" "}
              <select
                aria-label="Период протонного графика"
                value={snapshot ? data?.range : range}
                disabled={!!snapshot}
                onChange={(e) => setRange(e.target.value)}
              >
                {["6h", "1d", "3d", "7d"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            {!snapshot && (
              <button
                type="button"
                disabled={loading}
                onClick={() => setRefresh((n) => n + 1)}
              >
                Обновить протоны
              </button>
            )}
            {snapshot && <small>Сохранённые измерения на момент расчёта</small>}
            {loading && <span role="status">Загрузка измерений NOAA…</span>}
            {error && <span role="alert">{error}</span>}
          </div>
          {data && (
            <>
              <p
                className={data.status === "OK" ? "" : "protonwarning"}
                role="status"
              >
                {names[data.status] || data.status} · {data.message}
              </p>
              <div className="protonmetrics">
                {rows.map((r, i) => (
                  <div key={i}>
                    <span>Протоны ≥{energies[i]} MeV</span>
                    <strong>
                      {r?.flux == null ? "—" : r.flux.toPrecision(4)}{" "}
                      <small>pfu</small>
                    </strong>
                    <small>
                      GOES-{r?.satellite || "—"} · {stamp(r?.observed_at)}
                      {r?.is_stale ? " · устарело" : ""}
                    </small>
                    <p>
                      Пик:{" "}
                      {r?.peak
                        ? `${r.peak.flux.toPrecision(4)} pfu · ${stamp(r.peak.time)}`
                        : "—"}
                    </p>
                  </div>
                ))}
              </div>
              <div className="protoncontrols">
                <strong>NOAA S-scale: {data.noaa_scale.level || "—"}</strong>
                <span>Статус приложения: {data.internal_status}</span>
                <span>
                  Тренд ≥10 MeV за час: {names[data.trend] || data.trend}
                </span>
              </div>
              {data.warning_100mev && (
                <p className="protonwarning">
                  ≥100 MeV ≥1 pfu — превышен отдельный порог протонного
                  уведомления.
                </p>
              )}
              <div className="protoncontrols">
                {energies.map((e, i) => (
                  <label key={e} style={{ color: colors[i] }}>
                    <input
                      type="checkbox"
                      checked={enabled[i]}
                      onChange={() =>
                        setEnabled((v) => v.map((b, j) => (j === i ? !b : b)))
                      }
                    />{" "}
                    ≥{e} MeV
                  </label>
                ))}
              </div>
              {times.length > 0 ? (
                <>
                  <svg
                    className="protonchart"
                    viewBox="0 0 820 280"
                    role="img"
                    aria-label="Поток протонов pfu, логарифмическая шкала, время UTC"
                    onPointerMove={(event) => {
                      const r = event.currentTarget.getBoundingClientRect();
                      setCursor(
                        Math.max(
                          0,
                          Math.min(
                            100,
                            ((((event.clientX - r.left) / r.width) * 820 - 60) /
                              700) *
                              100,
                          ),
                        ),
                      );
                    }}
                  >
                    <text x="5" y="12">
                      pfu (log)
                    </text>
                    {[-3, -2, -1, 0, 1, 2, 3, 4, 5].map((p) => (
                      <g key={p}>
                        <line
                          x1="60"
                          x2="760"
                          y1={y(10 ** p)}
                          y2={y(10 ** p)}
                          stroke="#253449"
                        />
                        <text x="4" y={y(10 ** p) + 4}>
                          {10 ** p}
                        </text>
                        {p > 0 && enabled[0] && (
                          <text x="765" y={y(10 ** p) + 4}>
                            S{p}
                          </text>
                        )}
                      </g>
                    ))}
                    {rows.map(
                      (r, i) =>
                        enabled[i] && (
                          <g key={i}>
                            {r?.series.map((p, j, series) => {
                              const prev = series[j - 1];
                              return prev &&
                                p.flux > 0 &&
                                prev.flux > 0 &&
                                p.satellite === prev.satellite &&
                                Date.parse(p.time) - Date.parse(prev.time) <=
                                  600000 ? (
                                <line
                                  key={j}
                                  x1={x(Date.parse(prev.time))}
                                  x2={x(Date.parse(p.time))}
                                  y1={y(prev.flux)}
                                  y2={y(p.flux)}
                                  stroke={colors[i]}
                                  strokeWidth="1.7"
                                />
                              ) : null;
                            })}
                          </g>
                        ),
                    )}
                    <line
                      x1={x(cursorTime)}
                      x2={x(cursorTime)}
                      y1="20"
                      y2="240"
                      stroke="white"
                      strokeDasharray="3 3"
                    />
                    <text x="60" y="270">
                      {time(new Date(begin).toISOString())} UTC
                    </text>
                    <text x="660" y="270">
                      {time(new Date(end).toISOString())} UTC
                    </text>
                  </svg>
                  <label className="protoncursor">
                    Момент измерения{" "}
                    <input
                      aria-label="Момент протонного графика"
                      type="range"
                      min="0"
                      max="100"
                      value={cursor}
                      onChange={(e) => setCursor(Number(e.target.value))}
                    />
                  </label>
                  <div className="protoncontrols">
                    {rows.map((r, i) => {
                      const point = r?.series.reduce(
                        (a, b) =>
                          Math.abs(Date.parse(a.time) - cursorTime) <
                          Math.abs(Date.parse(b.time) - cursorTime)
                            ? a
                            : b,
                        r.series[0],
                      );
                      return (
                        <small key={i}>
                          ≥{energies[i]}:{" "}
                          {point
                            ? `${point.flux.toPrecision(4)} pfu · ${stamp(point.time)}`
                            : "—"}
                        </small>
                      );
                    })}
                  </div>
                  <small>
                    Уровни S1–S5 относятся только к ≥10 MeV. Нули не рисуются на
                    логарифмической оси; их значения доступны ползунком. Разрывы
                    более 10 минут не соединяются.
                  </small>
                </>
              ) : (
                <p>Нет пригодных точек для графика.</p>
              )}
              <details>
                <summary>Источник и объяснение статуса</summary>
                <p>
                  {data.source.provider} · {data.source.platform} ·{" "}
                  {data.source.role}
                </p>
                <a
                  href={data.source.endpoint || undefined}
                  target="_blank"
                  rel="noreferrer"
                >
                  Официальный dataset NOAA
                </a>
                <p>
                  Наблюдение: {stamp(data.observed_at)} · Получение:{" "}
                  {stamp(data.fetched_at)}
                </p>
                <p>
                  Возраст:{" "}
                  {data.freshness.age_seconds == null
                    ? "—"
                    : Math.round(data.freshness.age_seconds / 60)}{" "}
                  мин
                </p>
                {data.reasons.map((r, i) => (
                  <p key={i}>{r}</p>
                ))}
              </details>
            </>
          )}
          {!data && !loading && !error && (
            <p>Данные NOAA временно недоступны.</p>
          )}
        </>
      )}
    </section>
  );
}
