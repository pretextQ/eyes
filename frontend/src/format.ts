import type { Ratio } from "./types";

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}
export function shortId(id: string) {
  return id.slice(0, 8);
}
export function formatRatio(value?: Ratio) {
  return value && value.denominator > 0
    ? `${((value.numerator / value.denominator) * 100).toFixed(1)}%`
    : "—";
}
