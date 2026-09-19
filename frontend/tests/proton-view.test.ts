import { describe, it, expect } from "vitest";
import {
  hasAdverseAssessment,
  observationRequest,
  observationsForPeriod,
  protonRanges,
} from "../lib/proton-view";
import type { ProtonData } from "../app/ProtonPanel";

const now = Date.parse("2026-09-19T12:00:00Z");
describe("GOES range and historical policy", () => {
  it.each(protonRanges)(
    "current requests $value independently of EVA date",
    ({ value }) => {
      expect(
        observationRequest("current", "2024-05-10T13:00", 360, value, now),
      ).toEqual({ range: value });
    },
  );
  it("rejects unsupported API range", () =>
    expect(observationRequest("current", "", 60, "30d", now)).toBeNull());
  it.each(["historical_replay", "historical_review"])(
    "old %s never requests modern GOES",
    (mode) => {
      expect(
        observationRequest(mode, "2024-05-10T13:00", 360, "7d", now),
      ).toBeNull();
    },
  );
  it("selects the smallest rolling dataset covering the complete historical interval", () => {
    expect(
      observationRequest("historical_review", "2026-09-18T12:00", 60, "6h", now)
        ?.range,
    ).toBe("1d");
    expect(
      observationRequest("historical_review", "2026-09-12T12:00", 60, "6h", now)
        ?.range,
    ).toBe("7d");
    expect(
      observationRequest(
        "historical_review",
        "2026-09-12T11:59",
        60,
        "6h",
        now,
      ),
    ).toBeNull();
  });
  it.each([
    ["bad", 60],
    ["2026-09-19T11:30", 60],
    ["2026-09-19T10:00", -60],
  ])("rejects invalid/future interval %s", (start, duration) => {
    expect(
      observationRequest(
        "historical_review",
        String(start),
        Number(duration),
        "6h",
        now,
      ),
    ).toBeNull();
  });
  it("filters all channel data and peaks without copying the current NORMAL status", () => {
    const fixture = {
      status: "OK",
      internal_status: "NORMAL",
      channels: Object.fromEntries(
        [10, 50, 100].map((e) => [
          `gte_${e}_mev`,
          {
            series: [
              { time: "2026-09-19T10:00:00Z", flux: e, satellite: 18 },
              { time: "2026-09-19T10:05:00Z", flux: e + 1, satellite: 18 },
              { time: "2026-09-19T11:00:00Z", flux: 999, satellite: 19 },
            ],
            flux: 999,
            peak: { flux: 999, time: "2026-09-19T11:00:00Z" },
          },
        ]),
      ),
    } as unknown as ProtonData;
    const request = observationRequest(
      "historical_review",
      "2026-09-19T10:00",
      60,
      "6h",
      now,
    )!;
    const view = observationsForPeriod(fixture, request);
    for (const e of [10, 50, 100]) {
      expect(view.channels[`gte_${e}_mev`].peak?.flux).toBe(e + 1);
      expect(view.channels[`gte_${e}_mev`].satellite).toBe(18);
      expect(view.channels[`gte_${e}_mev`].series).toHaveLength(2);
    }
    expect(view.internal_status).toBe("UNKNOWN");
    const absent = observationsForPeriod(fixture, {
      ...request,
      start: now - 60000,
      end: now,
    });
    expect(absent.status).toBe("DATA_UNAVAILABLE");
    expect(absent.channels.gte_10_mev.flux).toBeNull();
    expect(fixture.channels.gte_10_mev.flux).toBe(999);
  });
});
describe("adverse presentation", () => {
  it("hides unused zero category", () =>
    expect(
      hasAdverseAssessment([
        { status: "attention", adverse_minutes: 0, intervals: [] },
      ]),
    ).toBe(false));
  it("preserves genuine adverse in older snapshots", () =>
    expect(
      hasAdverseAssessment([
        { status: "adverse", adverse_minutes: 60, intervals: [] },
      ]),
    ).toBe(true));
});
