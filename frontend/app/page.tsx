"use client";
import ProtonPanel from "./ProtonPanel";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronRight,
  Clock,
  Database,
  ExternalLink,
  Globe2,
  Layers,
  LoaderCircle,
  Orbit as OrbitIcon,
  RefreshCw,
  Satellite,
  ShieldAlert,
  Sun,
  Waypoints,
} from "lucide-react";
import OrbitTwin from "./OrbitTwin";
import { Evidence, Factor, Result, Source } from "../lib/types";
import { labels, mechanisms, stamp, time, intervalStyle } from "../lib/format";

const modes: Record<string, string> = {
  current: "Текущая обстановка",
  historical_replay: "Строгий replay",
  historical_review: "Исторический разбор",
};
const sections = [
  ["overview", "Обзор", Globe2],
  ["timeline", "Временная шкала", Activity],
  ["compare", "Сравнение окон", Layers],
  ["evidence", "Доказательства", Database],
] as const;
function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <i />
      {labels[status] || status}
    </span>
  );
}
function Fact({ factor, evidence }: { factor: Factor; evidence: Evidence[] }) {
  return (
    <details className="fact">
      <summary>
        <span>{mechanisms[factor.mechanism]}</span>
        <Badge status={factor.status} />
        <ChevronRight size={16} />
      </summary>
      <div className="factbody">
        <p>{factor.rule}</p>
        <p className="muted">
          Уверенность: {factor.confidence} ·{" "}
          {factor.confidence_reasons.join(" ")}
        </p>
        {factor.limitations.map((x) => (
          <p key={x} className="muted">
            {x}
          </p>
        ))}
        {factor.catalog_result === "no_events_in_available_catalog" && (
          <p>
            События не выявлены в доступном каталоге. Это отличается от
            отсутствия риска.
          </p>
        )}
        {factor.facts.map((f, i) => (
          <dl className="rawfacts" key={i}>
            {Object.entries(f)
              .filter(([k]) => k !== "original")
              .map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
          </dl>
        ))}
        {evidence
          .filter((e) => factor.evidence_ids.includes(e.raw_id))
          .map((e) => (
            <a key={e.raw_id} href={e.url} target="_blank" rel="noreferrer">
              {e.provider} / {e.product} <ExternalLink size={13} />
            </a>
          ))}
      </div>
    </details>
  );
}

function GroundTrack({ result }: { result: Result | null }) {
  const orbit = result?.orbit;
  const paths: string[] = [];
  let points: string[] = [];
  if (orbit)
    for (let i = 0; i < orbit.points.length; i++) {
      const p = orbit.points[i];
      if (i && Math.abs(p.lon - orbit.points[i - 1].lon) > 180) {
        paths.push(points.join(" "));
        points = [];
      }
      points.push(`${(p.lon + 180) * 2},${(90 - p.lat) * 2}`);
    }
  if (points.length) paths.push(points.join(" "));
  return (
    <div className="map">
      <div className="maptop">
        <span>
          <Globe2 size={15} /> ТРАЕКТОРИЯ МКС
        </span>
        <span>WGS84 · UTC</span>
      </div>
      <svg
        viewBox="0 0 720 360"
        role="img"
        aria-label="Проекция траектории МКС: долгота по горизонтали, широта по вертикали"
      >
        <defs>
          <pattern
            id="grid"
            width="60"
            height="60"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 60 0 L 0 0 0 60"
              fill="none"
              stroke="#193147"
              strokeWidth=".8"
            />
          </pattern>
          <radialGradient id="bg">
            <stop stopColor="#142c40" />
            <stop offset="1" stopColor="#081522" />
          </radialGradient>
        </defs>
        <rect width="720" height="360" fill="url(#bg)" />
        <rect width="720" height="360" fill="url(#grid)" />
        <line
          x1="0"
          y1="180"
          x2="720"
          y2="180"
          stroke="#2c4357"
          strokeDasharray="5 6"
        />
        {[-60, 0, 60].map((lat) => (
          <text
            key={lat}
            x="8"
            y={(90 - lat) * 2 - 7}
            fill="#678298"
            fontSize="10"
          >
            {lat}°
          </text>
        ))}
        {[-120, -60, 0, 60, 120].map((lon) => (
          <text
            key={lon}
            x={(lon + 180) * 2 + 5}
            y="348"
            fill="#678298"
            fontSize="10"
          >
            {lon}°
          </text>
        ))}
        {paths.map((p, i) => (
          <polyline
            key={i}
            points={p}
            fill="none"
            stroke="#4bc7f1"
            strokeWidth="2"
          />
        ))}
        {orbit && (
          <g
            transform={`translate(${(orbit.points[0].lon + 180) * 2},${(90 - orbit.points[0].lat) * 2})`}
          >
            <circle r="13" fill="#45c6f433" />
            <circle r="4" fill="#83e5ff" />
          </g>
        )}
      </svg>
      {!orbit && (
        <div className="mapempty">
          <OrbitIcon size={32} />
          <strong>
            {result ? "Траектория недоступна" : "Выберите окно ВКД"}
          </strong>
          <span>
            {result
              ? "Нужны орбитальные элементы соответствующего периода."
              : "После расчёта здесь появится реальная траектория МКС."}
          </span>
        </div>
      )}
      <div className="mapbottom">
        <span>
          <i className="dot" />{" "}
          {orbit ? "SGP4 · шаг 60 секунд" : "Ожидание расчёта"}
        </span>
        <span>{orbit ? `${orbit.points.length} точек` : "NORAD 25544"}</span>
      </div>
    </div>
  );
}

export default function Home() {
  const [section, setSection] = useState("overview"),
    [mode, setMode] = useState("current"),
    [start, setStart] = useState(""),
    [duration, setDuration] = useState(360),
    [horizon, setHorizon] = useState(720),
    [cutoff, setCutoff] = useState(""),
    [result, setResult] = useState<Result | null>(null),
    [sources, setSources] = useState<Source[]>([]),
    [loading, setLoading] = useState(false),
    [refreshing, setRefreshing] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState(0),
    [copied, setCopied] = useState(false);
  useEffect(() => {
    setStart(new Date().toISOString().slice(0, 16));
    fetch("/api/sources/status")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setSources)
      .catch(() => setError("Сервер недоступен. Проверьте запуск API."));
    const id = new URLSearchParams(location.search).get("analysis");
    if (id) {
      setLoading(true);
      fetch(`/api/analysis/${encodeURIComponent(id)}`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data: Result) => {
          setResult(data);
          setMode(data.request.mode);
          setStart(data.request.start_utc.slice(0, 16));
          setDuration(data.request.duration_minutes);
          setHorizon(data.request.search_horizon_minutes);
          setCutoff(data.request.cutoff_utc?.slice(0, 16) || "");
        })
        .catch(() => setError("Сохранённый расчёт не найден."))
        .finally(() => setLoading(false));
    }
  }, []);
  useEffect(() => {
    const timer = setInterval(
      () =>
        fetch("/api/sources/status")
          .then((r) => r.json())
          .then(setSources)
          .catch(() => {}),
      60000,
    );
    return () => clearInterval(timer);
  }, []);
  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          start_utc: start + ":00Z",
          duration_minutes: duration,
          search_horizon_minutes: horizon,
          cutoff_utc: mode === "historical_replay" ? cutoff + ":00Z" : null,
        }),
      });
      const data = await response.json();
      if (!response.ok)
        throw Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail),
        );
      setResult(data);
      setSelected(0);
      setSources(data.sources);
      history.replaceState(null, "", `?analysis=${data.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось выполнить расчёт");
    } finally {
      setLoading(false);
    }
  }
  async function refresh() {
    setRefreshing(true);
    setError("");
    try {
      const r = await fetch("/api/sources/refresh", { method: "POST" });
      const data = await r.json();
      if (!r.ok) throw Error(data.detail);
      setSources(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка обновления");
    } finally {
      setRefreshing(false);
    }
  }
  function setPlanMode(value: string) {
    setMode(value);
    if (value !== "current" && !start.startsWith("2024-")) {
      setStart("2024-05-10T13:00");
      setCutoff("2024-05-10T12:30");
    }
    if (value === "current") setStart(new Date().toISOString().slice(0, 16));
  }
  const window = result?.windows[selected];
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="/">
          <span className="brandmark">
            <OrbitIcon size={25} />
          </span>
          <div>
            ORBITAL <b>RISK</b>
            <span>RISK / EVA PLANNER</span>
          </div>
        </a>
        <div className="navlabel">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav>
          {sections.map(([id, label, Icon]) => (
            <button
              key={id}
              className={section === id ? "active" : ""}
              onClick={() => setSection(id)}
            >
              <Icon size={18} />
              {label}
              {section === id && <ChevronRight size={14} />}
            </button>
          ))}
        </nav>
        <button
          className="iconbutton navrefresh"
          title="Обновить источники"
          aria-label="Обновить источники"
          onClick={refresh}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? "spin" : ""} />
        </button>
        <div className="sidebarfoot">
          <div>
            <Satellite size={17} /> МКС · NORAD 25544
          </div>
          <p>
            Исследовательский прототип
            <br />
            поддержки решений
          </p>
          <span className="mono">
            ALGORITHM {result?.algorithm_version || "1.0.0"}
          </span>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Орбитальная аналитика <ChevronRight size={13} />
            <span>Планирование ВКД</span>
          </div>
          <div className="headeractions">
            <span className="utc">
              <Clock size={14} /> UTC
            </span>
            <button
              className="iconbutton"
              title="Обновить источники"
              aria-label="Обновить источники"
              onClick={refresh}
              disabled={refreshing}
            >
              <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            </button>
          </div>
        </header>
        <div className={`content view-${section}`}>
          <div className="pageheading">
            <div>
              <div className="eyebrow">EVA DECISION SUPPORT</div>
              <h1>Оценка орбитального риска</h1>
              <p>Внешняя обстановка. Сравнение окон. Проверяемые решения.</p>
            </div>
            <span className="prototype">Аналитический сервис</span>
          </div>
          <form className="panel query" onSubmit={analyze}>
            <div className="paneltitle">
              <span>
                <Waypoints size={18} /> Параметры окна
              </span>
              <small>Все даты и время в UTC</small>
            </div>
            <div className="fields">
              <label>
                Режим
                <select
                  aria-label="Режим"
                  value={mode}
                  onChange={(e) => setPlanMode(e.target.value)}
                >
                  {Object.entries(modes).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Начало ВКД · UTC
                <input
                  aria-label="Начало ВКД UTC"
                  type="datetime-local"
                  required
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
              <label>
                Длительность
                <select
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                >
                  {Array.from({ length: 8 }, (_, i) => (
                    <option key={i} value={(i + 1) * 60}>
                      {i + 1} ч
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Поиск альтернатив
                <select
                  value={horizon}
                  onChange={(e) => setHorizon(Number(e.target.value))}
                >
                  {[0, 60, 180, 360, 720, 1440].map((m) => (
                    <option key={m} value={m}>
                      {m / 60} ч
                    </option>
                  ))}
                </select>
              </label>
              {mode === "historical_replay" && (
                <label>
                  Отсечение · UTC
                  <input
                    aria-label="Отсечение UTC"
                    type="datetime-local"
                    required
                    value={cutoff}
                    onChange={(e) => setCutoff(e.target.value)}
                  />
                </label>
              )}
              <button className="primary" disabled={loading} type="submit">
                {loading ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Activity size={17} />
                )}{" "}
                {loading ? "Расчёт…" : "Рассчитать окно"}
              </button>
            </div>
            <p className="formnote">
              {mode === "historical_replay"
                ? "В расчёте используются только выпуски, опубликованные не позже отсечения."
                : mode === "historical_review"
                  ? "Разбор архивной обстановки. Не является прогнозом из прошлого."
                  : "Автообновление источников учитывает частоту публикации. Сохранённый расчёт остаётся неизменным."}{" "}
              Изменение длительности создаёт новый план.
            </p>
          </form>
          {error && (
            <div role="alert" className="error">
              <ShieldAlert size={18} />
              {error}
            </div>
          )}
          {loading && (
            <div role="status" className="loading">
              <LoaderCircle size={20} className="spin" /> Получаем данные и
              рассчитываем интервалы. Архивный запрос может занять несколько
              минут.
            </div>
          )}
          <div className="sourcebar">
            <span>ИСТОЧНИКИ</span>
            {sources.map((s) => (
              <span
                key={s.id}
                title={`${s.product}: ${labels[s.status] || s.status}. Последний успех: ${stamp(s.last_success)}`}
                className={`source ${s.status}`}
              >
                <i />
                {s.provider}
                {s.id === "swpc_forecast"
                  ? " / прогноз"
                  : s.id === "swpc_protons"
                    ? " / GOES"
                    : s.id === "swpc_scales"
                      ? " / SGR"
                      : s.id.startsWith("protons_")
                        ? ` / GOES ${s.id.includes("secondary") ? "secondary" : "primary"}`
                        : ""}
              </span>
            ))}
          </div>
          {result && (
            <div className="resultbar">
              <Badge status={result.status} />
              <span>Сохранён {stamp(result.created_at)}</span>
              <span className="mono">{result.id.slice(0, 8)}</span>
              <div className="exportactions">
                <button
                  onClick={async () => {
                    await navigator.clipboard.writeText(location.href);
                    setCopied(true);
                  }}
                >
                  {copied ? <Check size={14} /> : <ExternalLink size={14} />}{" "}
                  {copied ? "Скопировано" : "Ссылка"}
                </button>
                <a href={`/api/analysis/${result.id}/export.json`}>
                  <ArrowDownToLine size={14} />
                  JSON
                </a>
                <a href={`/api/analysis/${result.id}/report.pdf`}>
                  <ArrowDownToLine size={14} />
                  PDF
                </a>
              </div>
            </div>
          )}
          {section === "overview" && (
            <>
              <div className="overviewgrid">
                <section className="panel orbitpanel">
                  <OrbitTwin result={result} />
                  <details className="projection">
                    <summary>Открыть 2D-проекцию траектории</summary>
                    <GroundTrack result={result} />
                  </details>
                  <div className="orbitstats">
                    <div>
                      <span>Эпоха элементов</span>
                      <strong>{stamp(result?.orbit?.epoch)}</strong>
                    </div>
                    <div>
                      <span>Возраст к началу окна</span>
                      <strong>
                        {result?.orbit
                          ? `${result.orbit.age_hours.toFixed(1)} ч`
                          : "—"}
                      </strong>
                    </div>
                    <div>
                      <span>Режим геометрии</span>
                      <strong>
                        {result?.orbit?.geometry_mode || "Нет расчёта"}
                      </strong>
                    </div>
                  </div>
                  {result?.orbit && (
                    <details className="orbitdetails">
                      <summary>Система координат и ограничения</summary>
                      <p>{result.orbit.coordinates}</p>
                      {result.orbit.limitations.map((x) => (
                        <p key={x}>{x}</p>
                      ))}
                    </details>
                  )}
                </section>
                <section className="panel recommendation">
                  <div className="paneltitle">
                    <span>
                      <ShieldAlert size={18} /> Рекомендация
                    </span>
                  </div>
                  <div className="coveragegauge">
                    <svg viewBox="0 0 160 160">
                      <circle
                        cx="80"
                        cy="80"
                        r="65"
                        fill="none"
                        stroke="#1e2d40"
                        strokeWidth="7"
                      />
                      <circle
                        cx="80"
                        cy="80"
                        r="65"
                        fill="none"
                        stroke="#55c9f2"
                        strokeWidth="7"
                        strokeDasharray={`${((window?.factors.filter((f) => f.status !== "insufficient_data").length || 0) / 3) * 408} 408`}
                        transform="rotate(-90 80 80)"
                      />
                    </svg>
                    <strong>
                      {result
                        ? `${window?.factors.filter((f) => f.status !== "insufficient_data").length || 0}`
                        : "—"}
                      <small> / 3</small>
                    </strong>
                    <span>ЛИНИЙ С ДАННЫМИ</span>
                  </div>
                  <h2>
                    {result
                      ? labels[result.recommendation.status] ||
                        "Результат сравнения"
                      : "Решение начинается с данных"}
                  </h2>
                  <p>
                    {result?.recommendation.reason ||
                      "Задайте время выхода и допустимый период поиска. Сервис сопоставит окна одинаковой длительности."}
                  </p>
                  <div className="researchnote">
                    Не является разрешением на проведение ВКД. Индивидуальная
                    доза и риск повреждения скафандра не рассчитываются.
                  </div>
                  {result?.recommendation.window_status && (
                    <div className="resultsummary">
                      <p>
                        Исходное окно:{" "}
                        {labels[result.recommendation.window_status] ||
                          result.recommendation.window_status}
                      </p>
                      {result.recommendation.current_proton_status && (
                        <p>
                          Протоны сейчас:{" "}
                          {result.recommendation.current_proton_status} ·
                          наблюдения GOES
                        </p>
                      )}
                      <p>
                        {result.recommendation.confidence === "limited"
                          ? "Уверенность ограничена: доступна часть данных."
                          : "Оценка по покрытию источниками; точность прогноза не гарантируется."}
                      </p>
                      {!!result.recommendation.missing_factors?.length && (
                        <p>
                          Нет покрытия:{" "}
                          {result.recommendation.missing_factors.join(", ")}
                        </p>
                      )}
                    </div>
                  )}
                  {result && (
                    <button
                      className="textbutton"
                      onClick={() => setSection("compare")}
                    >
                      Посмотреть сравнение <ArrowRight size={16} />
                    </button>
                  )}
                </section>
              </div>
              <div className="factorcards">
                {["space_weather", "protons", "illumination"].map((m, i) => {
                  const f = window?.factors.find((f) => f.mechanism === m);
                  const Icon = [Activity, Waypoints, Sun][i];
                  return (
                    <section className="panel factorcard" key={m}>
                      <Icon size={20} />
                      <h3>{mechanisms[m]}</h3>
                      {f ? (
                        <>
                          <Badge status={f.status} />
                          <p>
                            {m === "illumination"
                              ? f.shadow_minutes !== undefined
                                ? `${f.shadow_minutes.toFixed(0)} мин в тени · условие работ`
                                : "Орбитальные данные отсутствуют"
                              : m === "protons"
                                ? f.forecast_probability_max != null
                                  ? `Прогноз S1: до ${f.forecast_probability_max}% · суточная вероятность`
                                  : `${f.facts.filter((r) => r.kind === "observation").length} измерений · прогноз S1 недоступен`
                                : `${f.attention_minutes.toFixed(0)} мин применимости предупреждающих условий`}
                          </p>
                        </>
                      ) : (
                        <p>Ожидание расчёта</p>
                      )}
                      <button
                        className="textbutton"
                        onClick={() => setSection("evidence")}
                      >
                        Данные и объяснения <ArrowRight size={14} />
                      </button>
                    </section>
                  );
                })}
              </div>
              <section className="panel weatherpanel">
                <div className="paneltitle">
                  <span>КОСМИЧЕСКАЯ ПОГОДА</span>
                  <small>NOAA SWPC / NCEI</small>
                </div>
                <div className="weathermetrics">
                  {[
                    ["Kp INDEX", "Kp", "index"],
                    ["R1–R2", "R1_R2_probability", "%"],
                    ["R3 OR GREATER", "R3_probability", "%"],
                  ].map(([label, metric, unit]) => {
                    const values =
                      window?.factors[0].facts
                        .filter((f) => f.metric === metric)
                        .map((f) => Number(f.value)) || [];
                    return (
                      <div key={metric}>
                        <span>{label}</span>
                        <strong>
                          {values.length ? Math.max(...values) : "—"}
                          <small>{unit === "%" ? "%" : ""}</small>
                        </strong>
                        <p>Максимум внешнего прогноза в окне</p>
                      </div>
                    );
                  })}
                </div>
                <div className="weatherexplanation">
                  <Activity size={25} />
                  <div>
                    <strong>Наблюдения и прогноз разделены</strong>
                    <p>
                      Суточная вероятность описывает весь период, а не точное
                      время события. Значения не являются дозой на МКС.
                    </p>
                    {result?.observations?.[0] && (
                      <small>{stamp(result.observations[0].start)}</small>
                    )}
                  </div>
                </div>
              </section>
            </>
          )}
          {(section === "overview" || section === "timeline") && (
            <ProtonPanel
              snapshot={result?.protons}
              historical={!!result && result.request.mode !== "current"}
            />
          )}
          {(section === "timeline" || section === "overview") && (
            <section className="panel timeline">
              <div className="paneltitle">
                <span>
                  <Activity size={18} /> Временная картина окна
                </span>
                {window && (
                  <small>
                    {time(window.start)} — {time(window.end)} UTC
                  </small>
                )}
              </div>
              {window ? (
                <>
                  <div className="timelineaxis">
                    <span>{time(window.start)}</span>
                    <span>{time(window.end)}</span>
                  </div>
                  {window.factors.map((f) => (
                    <div className="trackrow" key={f.mechanism}>
                      <div>
                        {mechanisms[f.mechanism]}
                        <small>{labels[f.status]}</small>
                      </div>
                      <div
                        className={`track ${f.status === "insufficient_data" ? "unknown" : ""}`}
                      >
                        {f.intervals.map((x, i) => (
                          <span
                            key={i}
                            className={`segment ${x.state}`}
                            style={intervalStyle(
                              x.start,
                              x.end,
                              window.start,
                              window.end,
                            )}
                            title={`${x.metric || x.state}: ${stamp(x.start)} — ${stamp(x.end)}${x.value !== undefined ? " · " + x.value + " " + x.unit : ""}`}
                          />
                        ))}
                        {!f.intervals.length && (
                          <span className="trackempty">
                            {f.status === "insufficient_data"
                              ? "Недостаточно данных"
                              : "Нет интервалов по правилу"}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="legend">
                    <span>
                      <i className="attention" /> Внимание / применимость
                      прогноза
                    </span>
                    <span>
                      <i className="sunlight" /> Свет
                    </span>
                    <span>
                      <i className="shadow" /> Тень
                    </span>
                    <span>
                      <i className="unknown" /> Неполнота
                    </span>
                  </div>
                  <p className="formnote">
                    Дорожки разных показателей могут перекрываться. Длительность
                    учитывает объединение интервалов, без повторного
                    суммирования.
                  </p>
                </>
              ) : (
                <div className="empty">
                  Временная шкала появится после расчёта.
                </div>
              )}
            </section>
          )}
          {section === "compare" && (
            <section className="panel">
              <div className="paneltitle">
                <span>
                  <Layers size={18} /> Сравнение окон
                </span>
                <small>Одинаковая длительность</small>
              </div>
              {result ? (
                <>
                  <div className="comparison">
                    {result.windows.map((w, i) => (
                      <button
                        className={`windowcard ${selected === i ? "chosen" : ""}`}
                        key={w.start}
                        onClick={() => setSelected(i)}
                      >
                        <div>
                          <span>
                            ОКНО {i + 1}
                            {i === 0 ? " · ИСХОДНОЕ" : ""}
                          </span>
                          {selected === i && <Check size={16} />}
                        </div>
                        <h3>
                          {time(w.start)} — {time(w.end)} UTC
                        </h3>
                        <p>
                          {stamp(w.start)} · {w.duration_minutes / 60} ч
                        </p>
                        {result.recommendation.best_indices?.includes(i) && (
                          <p>
                            {result.recommendation.status === "equal"
                              ? "Равен остальным по критериям"
                              : "В группе лучших по критериям"}
                          </p>
                        )}
                        {w.factors.map((f) => (
                          <div className="comparefactor" key={f.mechanism}>
                            <span>{mechanisms[f.mechanism]}</span>
                            <Badge status={f.status} />
                            <small>
                              Неблагоприятные условия: {f.adverse_minutes} мин ·
                              применимость условий внимания:{" "}
                              {f.attention_minutes} мин
                            </small>
                            {f.mechanism !== "illumination" &&
                              [
                                "Kp",
                                "R1_R2_probability",
                                "R3_probability",
                                "S1_probability",
                              ].map((metric) => {
                                const values = f.facts
                                  .filter(
                                    (x) =>
                                      x.metric === metric &&
                                      x.kind === "forecast",
                                  )
                                  .map((x) => Number(x.value))
                                  .filter(Number.isFinite);
                                const names: Record<string, string> = {
                                  Kp: "Kp",
                                  R1_R2_probability: "R1–R2",
                                  R3_probability: "R3+",
                                  S1_probability: "S1+",
                                };
                                return values.length ? (
                                  <small key={metric}>
                                    {names[metric]}: {Math.min(...values)}–
                                    {Math.max(...values)}
                                    {metric === "Kp"
                                      ? " · прогноз, шаг 3 ч"
                                      : "% · суточный прогноз"}
                                  </small>
                                ) : null;
                              })}
                          </div>
                        ))}
                      </button>
                    ))}
                  </div>
                  <p className="formnote">{result.recommendation.reason}</p>
                </>
              ) : (
                <div className="empty">
                  Сначала рассчитайте окно с горизонтом поиска больше нуля.
                </div>
              )}
            </section>
          )}
          {section === "evidence" && (
            <>
              <section className="panel">
                <div className="paneltitle">
                  <span>
                    <Database size={18} /> Объяснения и исходные значения
                  </span>
                </div>
                {window ? (
                  window.factors.map((f) => (
                    <Fact
                      key={f.mechanism}
                      factor={f}
                      evidence={result!.evidence}
                    />
                  ))
                ) : (
                  <div className="empty">
                    После расчёта здесь будут исходные значения, правила и
                    ссылки.
                  </div>
                )}
              </section>
              {result?.evidence.map((e) => (
                <section className="panel evidence" key={e.raw_id}>
                  <div className="paneltitle">
                    <span>
                      {e.provider} · {e.product}
                    </span>
                    <Badge status={e.stale ? "stale" : "available"} />
                  </div>
                  <dl>
                    <div>
                      <dt>Получено</dt>
                      <dd>{stamp(e.retrieved_at)}</dd>
                    </div>
                    <div>
                      <dt>Публикация</dt>
                      <dd>
                        {e.published_at
                          ? stamp(e.published_at)
                          : "См. published_at у фактов; для ряда источников неизвестна"}
                      </dd>
                    </div>
                    <div>
                      <dt>Версия парсера</dt>
                      <dd>{e.parser_version}</dd>
                    </div>
                    <div>
                      <dt>SHA-256</dt>
                      <dd className="mono hash">{e.sha256}</dd>
                    </div>
                  </dl>
                  <a href={e.url} target="_blank" rel="noreferrer">
                    Первоисточник <ExternalLink size={14} />
                  </a>
                  {e.provider !== "Space-Track" && (
                    <a
                      href={"/api" + e.raw_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Сохранённый ответ <ExternalLink size={14} />
                    </a>
                  )}
                </section>
              ))}
              {result?.warnings && (
                <section className="panel evidence">
                  <h3>Сообщения NOAA</h3>
                  {result.warnings.length ? (
                    result.warnings.map((w) => (
                      <details key={w.event_id}>
                        <summary>
                          {w.event_id} · {stamp(w.published_at)}
                          {w.stale ? " · устарело" : ""}
                        </summary>
                        <p>
                          {w.start && w.end
                            ? `${stamp(w.start)} — ${stamp(w.end)}`
                            : "Граница действия не определена — в интервал риска не включено"}
                        </p>
                        <pre>{w.value}</pre>
                      </details>
                    ))
                  ) : (
                    <p>
                      {result.warnings_status === "available"
                        ? "Нет сообщений, пересекающих окно, в полученной выдаче."
                        : "Недостаточно пригодных данных предупреждений для этого режима."}
                    </p>
                  )}
                </section>
              )}
              {result && (
                <section className="panel evidence">
                  <h3>Дополнительный контекст DONKI</h3>
                  <p>
                    Не участвует в строгом replay и не складывается с
                    предупреждениями NOAA.
                  </p>
                  <details>
                    <summary>Открыть {result.context.length} записей</summary>
                    <pre>{JSON.stringify(result.context, null, 2)}</pre>
                  </details>
                </section>
              )}
            </>
          )}
          {result && (
            <details className="panel limitations">
              <summary>Ограничения расчёта и статус источников</summary>
              {result.limitations.map((x) => (
                <p key={x}>{x}</p>
              ))}
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>
                      <th>Источник</th>
                      <th>Статус сейчас</th>
                      <th>Последний успех · UTC</th>
                      <th>Режим</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sources.map((s) => (
                      <tr key={s.id}>
                        <td>{s.product}</td>
                        <td>
                          <Badge status={s.status} />
                        </td>
                        <td>{stamp(s.last_success)}</td>
                        <td>{s.mode}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          <footer>
            <span>
              ORBITAL RISK <b> / </b> EVA PLANNING
            </span>
            <span>
              Проверяемые источники · Время UTC · Без симуляционных показателей
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
