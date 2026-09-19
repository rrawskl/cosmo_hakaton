"use client";
import { useEffect, useState } from "react";
import { stamp } from "../lib/format";
import {
  observationRequest,
  observationsForPeriod,
  protonRanges,
  ProtonRange,
} from "../lib/proton-view";
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
  HISTORICAL_OBSERVATIONS: "Измерения выбранного периода",
  RISING: "↑ Растущий",
  FALLING: "↓ Снижающийся",
  STABLE: "→ Стабильный",
  UNAVAILABLE: "Недостаточно измерений",
};
const energies = [10, 50, 100];
const colors = ["#66d9f1", "#b895ff", "#ffbc69"];
export default function ProtonPanel({
  mode = "current",
  start = "",
  duration = 360,
  saved = false,
}: {
  mode?: string;
  start?: string;
  duration?: number;
  saved?: boolean;
}) {
  const [response, setResponse] = useState<{
    key: string;
    data: ProtonData;
  } | null>(null);
  const [range, setRange] = useState<ProtonRange>("6h");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [enabled, setEnabled] = useState([true, true, true]);
  const [cursor, setCursor] = useState(100);
  const historical = mode !== "current";
  const request = observationRequest(mode, start, duration, range);
  const key = historical ? `${mode}/${start}/${duration}` : range;
  const data = request && response?.key === key ? response.data : null;
  useEffect(() => {
    const request = observationRequest(mode, start, duration, range);
    setError("");
    setResponse(null);
    setCursor(100);
    if (!request) {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const r = await fetch(`/api/protons/history?range=${request!.range}`, {
          signal: abort.signal,
        });
        if (!r.ok) throw Error(r.status === 422 ? "unsupported" : "request");
        const d = await r.json();
        if (
          d.range !== request!.range ||
          !d.channels ||
          !d.source ||
          !d.noaa_scale ||
          !d.freshness ||
          !Array.isArray(d.reasons) ||
          energies.some(
            (energy) => !Array.isArray(d.channels[`gte_${energy}_mev`]?.series),
          )
        )
          throw Error("response");
        if (active)
          setResponse({ key, data: observationsForPeriod(d, request!) });
      } catch (e) {
        if (active && !abort.signal.aborted) {
          setResponse(null);
          setError(
            e instanceof Error && e.message === "unsupported"
              ? "Этот диапазон не поддерживается источником данных."
              : "Не удалось связаться с API. Измерения недоступны; повторите обновление.",
          );
        }
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
  }, [range, refresh, mode, start, duration, key]);
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
        прямым измерением индивидуальной дозы космонавта. Диапазон графика —
        прошедшие наблюдения, не длительность ВКД и не прогноз.
      </p>
      {!request ? (
        <div role="status">
          <p>Исторические измерения GOES для выбранного периода недоступны.</p>
          <p>
            DATA_UNAVAILABLE / UNKNOWN. Оперативный rolling-архив NOAA GOES
            охватывает до 7 дней. Для более старых дат могут использоваться
            исторические прогнозы S1; измерения не подменяются современными
            данными.
          </p>
        </div>
      ) : (
        <>
          <div className="protoncontrols">
            {!historical && (
              <div
                className="protonranges"
                role="group"
                aria-label="Период протонного графика"
              >
                {protonRanges.map((r) => (
                  <button
                    key={r.value}
                    type="button"
                    aria-pressed={range === r.value}
                    onClick={() => setRange(r.value)}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            )}
            {historical && (
              <small>
                Измерения только выбранного периода: {stamp(start)} · {duration}{" "}
                мин
              </small>
            )}
            {
              <button
                type="button"
                disabled={loading}
                onClick={() => setRefresh((n) => n + 1)}
              >
                Обновить протоны
              </button>
            }
            {saved && !historical && (
              <small>
                Оперативные измерения сейчас. Сохранённые измерения расчёта
                остаются в JSON/PDF.
              </small>
            )}
            {loading && <span role="status">Загрузка измерений NOAA…</span>}
            {error && <span role="alert">{error}</span>}
          </div>
          {data && !loading && !error && (
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
                      {stamp(new Date(begin).toISOString())}
                    </text>
                    <text x="760" y="270" textAnchor="end">
                      {stamp(new Date(end).toISOString())}
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
