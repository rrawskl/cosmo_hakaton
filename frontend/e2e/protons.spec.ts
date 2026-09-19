import { test, expect } from "@playwright/test";
const makeData = (status = "OK", level = "BELOW_S1") => ({
  status,
  range: "6h",
  observed_at: "2026-09-19T05:15:00Z",
  fetched_at: "2026-09-19T05:16:00Z",
  message: "Synthetic test fixture only",
  source: {
    provider: "NOAA SWPC",
    platform: "GOES",
    role: "secondary",
    endpoint:
      "https://services.swpc.noaa.gov/json/goes/secondary/integral-protons-6-hour.json",
  },
  noaa_scale: { level },
  internal_status:
    status === "OK"
      ? level === "BELOW_S1"
        ? "NORMAL"
        : level === "S1"
          ? "ATTENTION"
          : "HIGH"
      : "UNKNOWN",
  trend: "STABLE",
  warning_100mev: false,
  freshness: { age_seconds: 60, stale: status !== "OK" },
  reasons: ["Test threshold"],
  channels: Object.fromEntries(
    [10, 50, 100].map((e) => [
      `gte_${e}_mev`,
      {
        flux:
          status === "DATA_UNAVAILABLE"
            ? null
            : level === "S3"
              ? 1000
              : level === "S1"
                ? 10
                : 0.2,
        unit: "pfu",
        observed_at: "2026-09-19T05:15:00Z",
        satellite: 19,
        is_stale: status !== "OK",
        trend: "STABLE",
        peak: null,
        series:
          status === "DATA_UNAVAILABLE"
            ? []
            : [
                { time: "2026-09-19T05:10:00Z", flux: 0.2, satellite: 19 },
                { time: "2026-09-19T05:15:00Z", flux: 0.3, satellite: 19 },
              ],
      },
    ]),
  ),
});
for (const [status, level] of [
  ["OK", "BELOW_S1"],
  ["OK", "S1"],
  ["OK", "S3"],
  ["DATA_STALE", "S1"],
  ["DATA_UNAVAILABLE", ""],
]) {
  test(`proton UI ${status} ${level}`, async ({ page }) => {
    await page.route("**/api/protons/history?*", (route) =>
      route.fulfill({
        json: {
          ...makeData(status, level),
          range: new URL(route.request().url()).searchParams.get("range"),
        },
      }),
    );
    await page.goto("/");
    const panel = page.getByRole("region", { name: "Протонная обстановка" });
    await expect(
      panel.getByText(
        `Статус приложения: ${status === "OK" ? (level === "BELOW_S1" ? "NORMAL" : level === "S1" ? "ATTENTION" : "HIGH") : "UNKNOWN"}`,
      ),
    ).toBeVisible();
    for (const width of [1920, 1440, 1366, 768, 390]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBeTruthy();
    }
    await panel.getByRole("button", { name: "1 день", exact: true }).click();
    await expect(
      panel.getByRole("button", { name: "1 день", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      panel.getByText("Статус приложения:", { exact: false }),
    ).toBeVisible();
    await panel
      .getByRole("checkbox", { name: "≥50 MeV", exact: true })
      .uncheck();
    await expect(
      panel.getByRole("checkbox", { name: "≥50 MeV", exact: true }),
    ).not.toBeChecked();
    if (status !== "DATA_UNAVAILABLE") {
      await panel.getByRole("slider").fill("50");
      await expect(panel.getByRole("slider")).toHaveValue("50");
    }
    await panel.getByRole("button", { name: "Обновить протоны" }).click();
  });
}
test("slow and failed proton API show states", async ({ page }) => {
  let release: () => void = () => {};
  const held = new Promise<void>((r) => (release = r));
  await page.route("**/api/protons/history?*", async (route) => {
    await held;
    await route.fulfill({ status: 503, body: "unavailable" });
  });
  await page.goto("/");
  await expect(page.getByText("Загрузка измерений NOAA…")).toBeVisible();
  release();
  await expect(
    page
      .getByRole("region", { name: "Протонная обстановка" })
      .getByRole("alert"),
  ).toContainText("Не удалось связаться");
});

test("range changes update real rendered series, all peaks and sources after saved current analysis", async ({
  page,
  request,
}) => {
  // A saved result exercises the previous disabled-select regression; NOAA values below are test fixtures only.
  const base = await request.post("/api/analysis", {
    data: {
      mode: "historical_replay",
      start_utc: "2024-05-10T13:00:00Z",
      cutoff_utc: "2024-05-10T12:30:00Z",
      duration_minutes: 360,
      search_horizon_minutes: 720,
    },
  });
  expect(base.ok()).toBeTruthy();
  const saved = await base.json();
  saved.request.mode = "current";
  saved.request.cutoff_utc = null;
  saved.protons = makeData();
  await page.route("**/api/analysis/test-current", (route) =>
    route.fulfill({ json: saved }),
  );
  const calls: string[] = [];
  await page.route("**/api/protons/history?*", async (route) => {
    const range = new URL(route.request().url()).searchParams.get("range")!;
    calls.push(range);
    const n = ["6h", "1d", "3d", "7d"].indexOf(range) + 1;
    const data = makeData();
    data.range = range;
    for (const energy of [10, 50, 100]) {
      const channel = data.channels[`gte_${energy}_mev`];
      channel.flux = energy * n;
      channel.satellite = 18 + n;
      channel.series = [
        { time: "2026-09-19T05:10:00Z", flux: energy * n, satellite: 18 + n },
        {
          time: "2026-09-19T05:15:00Z",
          flux: energy * n * 2,
          satellite: 18 + n,
        },
      ];
      Object.assign(channel, {
        peak: { flux: energy * n * 2, time: "2026-09-19T05:15:00Z" },
      });
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/?analysis=test-current");
  const panel = page.getByRole("region", { name: "Протонная обстановка" });
  await expect(
    panel.getByText("Оперативные измерения сейчас.", { exact: false }),
  ).toBeVisible();
  let previous = "";
  for (const [i, label] of ["6 часов", "1 день", "3 дня", "7 дней"].entries()) {
    if (i)
      await panel.getByRole("button", { name: label, exact: true }).click();
    await expect(
      panel.getByRole("button", { name: label, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    for (const [j, energy] of [10, 50, 100].entries()) {
      const card = panel.locator(".protonmetrics > div").nth(j);
      await expect(card).toContainText(
        `Пик: ${(energy * (i + 1) * 2).toPrecision(4)} pfu`,
      );
      await expect(card).toContainText(`GOES-${19 + i}`);
      await expect(card).toContainText("19.09.2026, 05:15");
    }
    const plotted = await panel.locator(".protonchart").innerHTML();
    expect(plotted).not.toBe(previous);
    previous = plotted;
    expect(calls).toContain(["6h", "1d", "3d", "7d"][i]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    panel.getByRole("button", { name: "7 дней", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/proton-ranges-mobile.png",
    fullPage: true,
  });
  await page.route("**/api/protons/history?range=1d", (route) =>
    route.fulfill({ status: 422, body: '{"detail":"internal test error"}' }),
  );
  await panel.getByRole("button", { name: "1 день", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText(
    "Этот диапазон не поддерживается",
  );
  await expect(panel.getByRole("img")).toHaveCount(0);
  await expect(panel).not.toContainText("internal test error");
});

test("old historical selections hide modern observations before calculation", async ({
  page,
}) => {
  let calls = 0;
  await page.route("**/api/protons/history?*", (route) => {
    calls++;
    return route.fulfill({ json: makeData() });
  });
  await page.goto("/");
  const panel = page.getByRole("region", { name: "Протонная обстановка" });
  await expect(panel.getByRole("img")).toBeVisible();
  for (const mode of ["historical_replay", "historical_review"]) {
    await page
      .getByRole("combobox", { name: "Режим", exact: true })
      .selectOption(mode);
    await page.getByLabel("Начало ВКД UTC").fill("2024-05-10T13:00");
    const before = calls;
    await expect(panel).toContainText(
      "Исторические измерения GOES для выбранного периода недоступны",
    );
    await expect(panel).toContainText("DATA_UNAVAILABLE / UNKNOWN");
    await expect(panel.getByRole("img")).toHaveCount(0);
    await expect(panel).not.toContainText("NORMAL");
    await expect(panel).not.toContainText("0 pfu");
    expect(calls).toBe(before);
  }
});
test("live NOAA through API to graph, navigation and console", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const response = await request.get("/api/protons/current");
  expect(response.status()).toBe(200);
  const live = await response.json();
  expect(live.status).toBe("OK");
  await page.goto("/");
  const panel = page.getByRole("region", { name: "Протонная обстановка" });
  await expect(
    panel.getByText("Актуальные данные", { exact: false }),
  ).toBeVisible();
  for (const energy of [10, 50, 100]) {
    const v = live.channels[`gte_${energy}_mev`].flux;
    await expect(
      panel
        .getByText(`${Number(v).toPrecision(4)} pfu`, { exact: true })
        .first(),
    ).toBeVisible();
  }
  await expect(panel.getByRole("img")).toBeVisible();
  await panel.locator("summary").click();
  await expect(panel.getByText("Официальный dataset NOAA")).toBeVisible();
  await page.screenshot({
    path: "test-results/protons-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/protons-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
