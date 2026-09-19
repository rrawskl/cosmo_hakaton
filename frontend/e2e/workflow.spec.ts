import { test, expect } from "@playwright/test";
test("historical replay, evidence, saved JSON and responsive layout", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page
    .getByRole("combobox", { name: "Режим", exact: true })
    .selectOption("historical_replay");
  await page.getByLabel("Начало ВКД UTC").fill("2024-05-10T13:00");
  await page.getByLabel("Отсечение UTC").fill("2024-05-10T12:30");
  const responsePromise = page.waitForResponse(
    (r) => r.url().endsWith("/api/analysis") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Рассчитать окно" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.recommendation.status).not.toBe("insufficient_data");
  expect(result.protons).toBeNull();
  expect(
    result.windows[0].factors.find(
      (f: { mechanism: string }) => f.mechanism === "protons",
    ).forecast_probability_max,
  ).toBe(55);
  const protonPanel = page.getByRole("region", {
    name: "Протонная обстановка",
  });
  await expect(protonPanel).toContainText("DATA_UNAVAILABLE / UNKNOWN");
  await expect(protonPanel.getByRole("img")).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: /Варианты равнозначны|Предпочтительный вариант/,
    }),
  ).toBeVisible();
  const json = await request.get(`/api/analysis/${result.id}/export.json`);
  expect(await json.json()).toEqual(result);
  await page
    .getByRole("button", { name: "Сравнение окон", exact: true })
    .click();
  await expect(page.locator(".windowcard")).toHaveCount(3);
  await expect(page.locator(".comparison")).not.toContainText(
    "Неблагоприятные условия: 0",
  );
  await expect(page.locator(".comparison")).toContainText(
    "применимость условий внимания: 360 мин",
  );
  await expect(page.locator(".windowcard").first()).toContainText("Kp:");
  await expect(page.locator(".windowcard").first()).toContainText("S1+:");
  await page.screenshot({
    path: "test-results/comparison.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Доказательства", exact: true })
    .click();
  await page.locator(".fact").first().locator("summary").click();
  await expect(page.getByText("Kp", { exact: true }).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  for (const select of await page.locator(".query select").all()) {
    expect((await select.boundingBox())!.width).toBeGreaterThan(110);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Обзор", exact: true }).click();
  await page.screenshot({ path: "test-results/overview.png", fullPage: true });
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: /Варианты равнозначны|Предпочтительный вариант/,
    }),
  ).toBeVisible();
});
