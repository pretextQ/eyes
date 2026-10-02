import type { Ratio } from "./types";

export function formatDate(value?: string | null) {
  return value
    ? new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(value))
    : "—";
}
export function shortId(id: string) {
  return id.slice(0, 8);
}
export function formatRatio(value?: Ratio) {
  return value && value.denominator > 0
    ? `${((value.numerator / value.denominator) * 100).toFixed(1)}%`
    : "—";
}
