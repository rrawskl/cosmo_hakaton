import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Orbital Risk — Планирование ВКД",
  description:
    "Исследовательский сервис анализа внешних воздействий на окно ВКД",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
