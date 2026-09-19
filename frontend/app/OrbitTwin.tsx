"use client";
import { useEffect, useState } from "react";
import { Pause, Play, Orbit, Sun, Satellite } from "lucide-react";
import { Result } from "../lib/types";
import { stamp, time } from "../lib/format";

export default function OrbitTwin({ result }: { result: Result | null }) {
  const [index, setIndex] = useState(0),
    [playing, setPlaying] = useState(false);
  const points = result?.orbit?.points || [];
  const point = points[Math.min(index, points.length - 1)];
  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [result?.id]);
  useEffect(() => {
    if (!playing || !points.length) return;
    const timer = setInterval(
      () => setIndex((i) => (i + 1) % points.length),
      150,
    );
    return () => clearInterval(timer);
  }, [playing, points.length]);
  const project = (lat: number, lon: number, r = 112) => {
    const phi = (lat * Math.PI) / 180,
      theta = (lon * Math.PI) / 180;
    return {
      x: 300 + r * Math.cos(phi) * Math.sin(theta),
      y: 180 - r * Math.sin(phi),
      z: Math.cos(phi) * Math.cos(theta),
    };
  };
  const path = (coords: { lat: number; lon: number; altitude_km?: number }[]) =>
    coords
      .map((p, i) => {
        const v = project(
          p.lat,
          p.lon,
          p.altitude_km ? 112 * (1 + p.altitude_km / 6378.137) : 112,
        );
        return `${i ? "L" : "M"}${v.x.toFixed(2)},${v.y.toFixed(2)}`;
      })
      .join(" ");
  const visible: (typeof points)[] = [];
  let segment: typeof points = [];
  for (const p of points) {
    if (project(p.lat, p.lon).z >= 0) {
      segment.push(p);
    } else if (segment.length) {
      visible.push(segment);
      segment = [];
    }
  }
  if (segment.length) visible.push(segment);
  const p = point
    ? project(point.lat, point.lon, 112 * (1 + point.altitude_km / 6378.137))
    : null;
  return (
    <section className="twin">
      <div className="twinheading">
        <div>
          <div className="eyebrow">EVA ORBIT MODEL</div>
          <h2>Траектория и условия работ</h2>
        </div>
        <span className="modeltag">
          {point ? "● SGP4 / РАСЧЁТ" : "○ ОЖИДАНИЕ ДАННЫХ"}
        </span>
      </div>
      <div className="twinbody">
        <div className="globeview">
          <svg
            viewBox="0 0 600 360"
            role="img"
            aria-label="Ортографическая проекция реальной траектории МКС; переднее полушарие выделено"
          >
            <defs>
              <radialGradient id="earth">
                <stop offset="0" stopColor="#133c56" />
                <stop offset=".85" stopColor="#0a2338" />
                <stop offset="1" stopColor="#123e5a" />
              </radialGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" />
              </filter>
            </defs>
            <circle
              cx="300"
              cy="180"
              r="116"
              fill="#2273a322"
              filter="url(#glow)"
            />
            <circle
              cx="300"
              cy="180"
              r="112"
              fill="url(#earth)"
              stroke="#205271"
            />
            {[-60, -30, 0, 30, 60].map((lat) => (
              <path
                key={"lat" + lat}
                d={path(
                  Array.from({ length: 91 }, (_, i) => ({
                    lat,
                    lon: i * 2 - 90,
                  })),
                )}
                fill="none"
                stroke="#28516a"
                strokeWidth=".7"
              />
            ))}
            {[-75, -45, -15, 15, 45, 75].map((lon) => (
              <path
                key={"lon" + lon}
                d={path(
                  Array.from({ length: 91 }, (_, i) => ({
                    lat: i * 2 - 90,
                    lon,
                  })),
                )}
                fill="none"
                stroke="#28516a"
                strokeWidth=".7"
              />
            ))}
            {points.length > 0 && (
              <path
                d={path(points)}
                stroke="#287291"
                fill="none"
                strokeWidth=".8"
                strokeDasharray="3 4"
                opacity=".35"
              />
            )}
            {visible.map((s, i) => (
              <path
                key={i}
                d={path(s)}
                stroke="#6ad4f5"
                fill="none"
                strokeWidth="1.4"
                opacity=".8"
              />
            ))}
            {p && (
              <g
                transform={`translate(${p.x},${p.y})`}
                opacity={p.z >= 0 ? 1 : 0.35}
              >
                <circle r="12" fill="#49c9f633" stroke="#64d5ef" />
                <circle r="4" fill="#bcf3ff" />
                <text x="17" y="4" fill="#b5efff" fontSize="9">
                  ISS
                </text>
              </g>
            )}
            <text
              x="300"
              y="184"
              fill="#73a6bc"
              textAnchor="middle"
              fontSize="9"
              fontFamily="monospace"
            >
              EARTH · WGS84
            </text>
            {!point && (
              <text
                x="300"
                y="325"
                textAnchor="middle"
                fill="#7890a8"
                fontSize="10"
              >
                {result
                  ? "Орбитальные элементы не предоставлены"
                  : "Выполните расчёт окна"}
              </text>
            )}
          </svg>
          <div className="globekey">
            <span>● ISS POSITION</span>
            <span>Траектория по реальным элементам · без шкалы риска</span>
          </div>
          <div className="playback">
            <button
              aria-label={
                playing ? "Остановить траекторию" : "Воспроизвести траекторию"
              }
              disabled={!points.length}
              onClick={() => setPlaying(!playing)}
            >
              {playing ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <input
              aria-label="Момент на траектории"
              type="range"
              min="0"
              max={Math.max(0, points.length - 1)}
              value={index}
              disabled={!points.length}
              onChange={(e) => {
                setPlaying(false);
                setIndex(Number(e.target.value));
              }}
            />
            <span>{point ? time(point.time) + " UTC" : "—"}</span>
          </div>
        </div>
        <div className="twinreadout">
          <div>
            <span>ВЫСОТА НАД WGS84</span>
            <strong>
              {point ? point.altitude_km.toFixed(1) : "—"}
              <small> км</small>
            </strong>
            <p>Вычислено SGP4 → ITRS</p>
          </div>
          <div>
            <span>ОСВЕЩЁННОСТЬ</span>
            <strong className="lit">
              <Sun size={20} />
              {point ? (point.shadow ? "Тень" : "Свет") : "Нет данных"}
            </strong>
            <p>Условие работ, не оценка опасности</p>
          </div>
          <div>
            <span>ПОЛОЖЕНИЕ</span>
            <strong className="coordinates">
              {point
                ? `${point.lat.toFixed(2)}° / ${point.lon.toFixed(2)}°`
                : "—"}
            </strong>
            <p>Широта / долгота</p>
          </div>
          <div>
            <span>МОМЕНТ РАСЧЁТА</span>
            <p>{point ? stamp(point.time) : "Ожидание расчёта"}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
