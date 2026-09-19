# Отчёт об изменениях версии 2.0.0

## 1. Исходное состояние

Next.js/React/TypeScript, FastAPI, SQLAlchemy/Alembic, SQLite локально и Compose
PostgreSQL. Работали SGP4, Space-Track replay, прогнозы SWPC/NCEI, DONKI контекст,
сохранённые результаты, JSON/PDF и адаптивный интерфейс. Второй фактор был
неполным каталогом сближений; протоны показывались одним каналом без fallback.
Git отсутствовал; инициализирован main и указан существующий целевой origin.

## 2–5. Изменённые и добавленные файлы, удаление старого фактора

Изменены backend/app/{config,parsers,adapters,analysis,api,exports}.py,
frontend/app/{page.tsx,globals.css}, frontend/lib/{types,format}.ts,
backend/tests/{test_api,test_parsers}.py, fixtures/manifest.json, compose.yaml,
.env.example, .gitignore, README и docs, scripts/experiments.py.
Добавлены backend/app/protons.py, backend/tests/test_protons.py,
fixtures/protons-{primary,secondary}.json, frontend/app/ProtonPanel.tsx,
frontend/e2e/protons.spec.ts и этот отчёт.

MMOD удалён из активного scoring, адаптера, парсера, графиков, карточек,
новых exports и тестов; fixture SOCRATES удалён. Старые пользовательские
snapshot в локальной приватной БД не переписываются. Они не участвуют в
новых вычислениях, имеют версию 1.0.0; текущая версия 2.0.0. Пустая БД при
клонировании создаёт только действующие источники. Старые записи источников
исключены из активного API статусов без разрушения сохранённых расчётов.

## 6–10. Proton Environment, источники, endpoints, fallback, шкала

Официальные GOES integral-protons JSON primary/secondary, ranges 6h/1d/3d/7d.
Нормализация энергии/времени/спутника/pfu, фильтрация повреждённых точек,
серверный кеш, timeout/retry. Endpoint /protons/current и /protons/history;
браузер использует /api-префикс. Primary → validation/freshness → secondary;
при двойном отказе stale-кеш маркируется, отсутствие возвращает unavailable.

≥10 MeV: <10 BELOW_S1; ≥10 S1; ≥100 S2; ≥1000 S3; ≥10000 S4; ≥100000 S5.
≥100 MeV ≥1 pfu — отдельное warning condition. ≥50 MeV отображается без
придуманного порога. Источник, спутник, observed/fetched timestamps и SHA
сохраняются. Сглаженный часовой тренд и пики считаются из реального ряда.

## 11–12. Общая оценка и отсутствие double counting

Kp/R в первом факторе, протонные измерения во втором, свет/тень отдельно.
S1-прогноз и proton/radiation warnings не участвуют в первом факторе.
DONKI — контекст без суммирования. Внутренний статус приложения отделён от
NOAA S-scale. Оценка окон детерминирована; недостающие измерения не дают
благоприятного заключения. Будущее не экстраполируется из текущих наблюдений.

## 13–15. Тесты и сборка

Границы всех S-levels, 100MeV threshold, malformed/null/NaN, единицы, время,
дубликаты, timeout, cache, fallback, stale, trend, API и risk engine.
92 backend-теста прошли. 4 frontend unit-теста и браузерные сценарии описаны
в VALIDATION.md. Production Next.js и TypeScript проверены.
Живой NOAA → backend → API → frontend → график проверен без mocks.
Сохранённый новый расчёт повторно вычислен без сети: matches=true.

## 16–17. Найденные и исправленные проблемы

- Протонный парсер принимал лишь ≥10 MeV, не фильтровал NaN/единицы:
  заменён нормализованным парсером трёх каналов.
- Не было secondary fallback и проверки свежести каждого канала: добавлены.
- Потенциальный двойной учёт S1 и протонных предупреждений: исключён.
- .env.example был ориентирован на Docker и ломал простой локальный запуск:
  по умолчанию SQLite и localhost; Compose задаёт свои адреса.
- Опорная дата анализа фиксировалась после вычислений: теперь freshness
  и offline reproduce используют один и тот же момент начала расчёта.
- UI-test ошибки ловил служебный alert Next.js: селектор ограничен панелью.

## 18. Оставшиеся ограничения

Нет подключённого архива GOES за 2024, нет протонного прогноза/дозиметрии.
Нет гарантий внешней доступности NOAA/CelesTrak. Нет Docker в среде для
проверки контейнерного запуска; нет выбранного публичного веб-хостинга.
Расчёты орбиты без манёвров/полутени; инженерная граница эпохи 72 часа.
Все ограничения отображаются или документированы; случайных данных нет.

## Запуск и загрузка

Пошаговый Windows/PowerShell гайд, отдельные команды frontend/backend,
Docker, тестов, production build, troubleshooting, GitHub/GitVerse — в README.md.
Целевой remote: https://github.com/rrawskl/cosmo_hakaton.git, ветка main.
Локальный .env не входит в Git. Точные результаты commit/push указаны в
итоговом сообщении, поскольку их нельзя достоверно записать до выполнения.
