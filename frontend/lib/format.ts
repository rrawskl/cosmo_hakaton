export const labels: Record<string, string> = {
  favorable: "Без триггеров правила",
  attention: "Требует внимания",
  adverse: "Неблагоприятно",
  insufficient_data: "Недостаточно данных",
  not_applicable: "Условие работ",
  available: "Доступен",
  stale: "Устаревшие данные",
  failed: "Ошибка источника",
  disabled: "Отключён",
  partial: "Частичный результат",
  complete: "Расчёт завершён",
  equal: "Варианты равнозначны",
  preferred: "Предпочтительный вариант",
};
export const mechanisms: Record<string, string> = {
  space_weather: "Космическая погода",
  protons: "Протонная обстановка",
  illumination: "Свет и тень",
};
function asUTC(value: string) {
  return value.includes("T") && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value)
    ? value + "Z"
    : value;
}
export function stamp(value: string | null | undefined) {
  return value
    ? new Date(asUTC(value)).toLocaleString("ru-RU", {
        timeZone: "UTC",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }) + " UTC"
    : "Не предоставлено";
}
export function time(value: string) {
  return new Date(asUTC(value)).toLocaleTimeString("ru-RU", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
  });
}
export function intervalStyle(
  start: string,
  end: string,
  a: string,
  b: string,
) {
  const duration = Date.parse(b) - Date.parse(a);
  return {
    left: `${Math.max(0, ((Date.parse(start) - Date.parse(a)) / duration) * 100)}%`,
    width: `${Math.max(0.4, ((Date.parse(end) - Date.parse(start)) / duration) * 100)}%`,
  };
}
