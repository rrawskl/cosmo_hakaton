# Проверки версии 2.0.0

- Backend: 92 tests passed; два предупреждения зависимостей Starlette/AnyIO.
- Пороговые пары 9.999/10, 99.999/100, 999.999/1000, 9999.999/10000,
  99999.999/100000 проверены; отдельный ≥100 MeV ≥1 pfu проверен.
- Проверены три энергии, ordering, duplicates/conflicts, units, NaN/null,
  отрицательные значения, malformed JSON, future/stale, rising/falling/stable,
  timeout/retry, primary failure, secondary fallback, both unavailable, cache,
  window coverage, отсутствие прогноза из наблюдений и двойного учёта S1.
- Regression: SGP4 Vallado, исторический cutoff, JSON/PDF, сохранение,
  независимая тестовая БД, закрытый admin endpoint и отказ источников.
- Frontend: 4 Vitest. Playwright: 8 сценариев; состояния NORMAL/S1/S3, stale/unavailable,
  slow/error API, live NOAA без mocks, исторический replay и export.
  Размеры: 1920, 1440, 1366, 768, 390px; горизонтального overflow нет.
- Next production build/TypeScript проходит.
- Живой /protons/current: HTTP200, primary GOES-18, observed_at
  2026-09-19T05:20:00Z, ≥10=0.2496662586927414; ≥50=0.2298649549484253;
  ≥100=0.2284029722213745 pfu, BELOW_S1/NORMAL. Это зафиксированная проверка,
  не встроенные рабочие значения. NOAA ответ показан в браузерном графике.
- Все четыре живых диапазона 6h/1d/3d/7d ответили HTTP200/OK.
- Новый current-анализ содержит space_weather/protons/illumination.
  JSON равен snapshot; POST reproduce matches=true без сети; PDF создан.
- Реальные исторические орбиты проверены ранее на 1 мая, 10 мая, 20 июня 2024;
  исторический replay повторно проверяется браузерным regression-тестом.
- Эксперимент NOAA Kp на двух исторических эпизодах сохранён в
  data/experiments/results.json; это не оценка точности протонного прогноза.

## Ограничения

Протонный rolling API не содержит 2024 год. Для него DATA_UNAVAILABLE.
Наблюдения GOES не прогнозируют будущие часы ВКД, не измеряют дозу на МКС;
поэтому уверенного выбора будущего окна может не быть. Это ожидаемый результат.
NOAA/CelesTrak могут быть недоступны; состояние видно пользователю.
Docker Desktop отсутствует: Compose/PostgreSQL runtime не проверен.
Внешний сервер/домен не предоставлен, публикация веб-приложения не выполнялась.
