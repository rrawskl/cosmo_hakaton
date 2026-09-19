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
      route.fulfill({ json: makeData(status, level) }),
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
    await panel.getByRole("combobox").selectOption("1d");
    await expect(panel.getByRole("combobox")).toHaveValue("1d");
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
