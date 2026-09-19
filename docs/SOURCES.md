# Источники

| Источник | Использование | Доступ |
|---|---|---|
| NOAA GOES primary/secondary integral-protons | 10/50/100 MeV, pfu, 6h/1d/3d/7d | Публичный HTTPS, без ключа |
| NOAA SWPC 3-Day Forecast | Kp и R-прогноз, Issued | Публичный HTTPS |
| NOAA SWPC alerts/scales | Предупреждения и контекст | Публичный HTTPS |
| NOAA NCEI dated SWPC bulletins | Strict replay по Issued | Публичный HTTPS, есть пропуски |
| CelesTrak GP OMM ISS 25544 | Текущая орбита SGP4 | Публичный HTTPS, TTL2ч |
| Space-Track GP_HISTORY | Историческая орбита, CREATION_DATE | Локальные credentials; raw не публикуется |
| NASA DONKI SEP | Контекст, не scoring | NASA_API_KEY, по умолчанию DEMO_KEY |

Официальные описания:
- https://www.swpc.noaa.gov/products/goes-proton-flux
- https://www.swpc.noaa.gov/noaa-scales-explanation
- https://www.swpc.noaa.gov/products/notifications-timeline
- https://services.swpc.noaa.gov/json/goes/primary/
- https://services.swpc.noaa.gov/json/goes/secondary/
- https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/
- https://celestrak.org/NORAD/documentation/gp-data-formats.php
- https://www.space-track.org/documentation
- https://ccmc.gsfc.nasa.gov/tools/DONKI/

19 сентября 2026 оба 6-hour потока ответили HTTP200; primary GOES-18,
secondary GOES-19; поля time_tag/satellite/energy/flux. Идентификация энергии
по строковому полю, не позиции. Измерения отсутствующих каналов не выдумываются.
Каждый сырой ответ сохраняется с URL, SHA-256, временем получения, parser version.
Fixtures manifest содержит происхождение тестовых копий; production их не читает.
Исторические GOES за 2024 не поддержаны; NCEI-прогноз S1 не выдаётся за измерение.
