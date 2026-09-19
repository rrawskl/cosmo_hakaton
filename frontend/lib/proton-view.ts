import type { ProtonData } from "../app/ProtonPanel";

export const protonRanges = [
  { value: "6h", label: "6 часов", hours: 6 },
  { value: "1d", label: "1 день", hours: 24 },
  { value: "3d", label: "3 дня", hours: 72 },
  { value: "7d", label: "7 дней", hours: 168 },
] as const;
export type ProtonRange = (typeof protonRanges)[number]["value"];
export type ObservationRequest = {
  range: ProtonRange;
  start?: number;
  end?: number;
};

export function observationRequest(
  mode: string,
  start: string,
  duration: number,
  range: string,
  now = Date.now(),
): ObservationRequest | null {
  if (mode === "current") {
    return protonRanges.some((r) => r.value === range)
      ? { range: range as ProtonRange }
      : null;
  }
  if (!["historical_replay", "historical_review"].includes(mode)) return null;
  const a = Date.parse(
    /[Zz]|[+-]\d{2}:\d{2}$/.test(start) ? start : `${start}Z`,
  );
  const b = a + duration * 60000;
  if (
    !Number.isFinite(a) ||
    !Number.isFinite(duration) ||
    duration <= 0 ||
    b > now ||
    a >= b
  )
    return null;
  const supported = protonRanges.find((r) => a >= now - r.hours * 3600000);
  return supported ? { range: supported.value, start: a, end: b } : null;
}

export function observationsForPeriod(
  data: ProtonData,
  request: ObservationRequest,
): ProtonData {
  if (request.start === undefined || request.end === undefined) return data;
  const channels = Object.fromEntries(
    Object.entries(data.channels).map(([name, channel]) => {
      const series = channel.series
        .filter(
          (p) =>
            Date.parse(p.time) >= request.start! &&
            Date.parse(p.time) < request.end!,
        )
        .sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
      const last = series.at(-1);
      const peak = series.reduce<(typeof series)[number] | undefined>(
        (best, row) => (!best || row.flux > best.flux ? row : best),
        undefined,
      );
      return [
        name,
        {
          ...channel,
          series,
          flux: last?.flux ?? null,
          observed_at: last?.time ?? null,
          satellite: last?.satellite ?? null,
          trend: "UNAVAILABLE",
          peak: peak ? { flux: peak.flux, time: peak.time } : null,
        },
      ];
    }),
  );
  const present = Object.values(channels).some((c) => c.series.length > 0);
  return {
    ...data,
    channels,
    status: present
      ? data.status === "DATA_STALE"
        ? "DATA_STALE"
        : "HISTORICAL_OBSERVATIONS"
      : "DATA_UNAVAILABLE",
    observed_at: null,
    internal_status: "UNKNOWN",
    noaa_scale: { level: null },
    trend: "UNAVAILABLE",
    warning_100mev: null,
    message: present
      ? "Измерения выбранного периода. Получены сейчас; не используются для прогноза в строгом replay."
      : "Для выбранного периода измерения GOES недоступны.",
    reasons: [
      "Показаны только точки внутри выбранного периода; текущий статус и текущий тренд не перенесены в прошлое.",
    ],
  };
}

export function hasAdverseAssessment(
  factors: {
    status: string;
    adverse_minutes: number;
    intervals: { state: string }[];
  }[],
) {
  return factors.some(
    (f) =>
      f.status === "adverse" ||
      f.adverse_minutes > 0 ||
      f.intervals.some((i) => i.state === "adverse"),
  );
}
