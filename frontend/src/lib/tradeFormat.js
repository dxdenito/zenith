export const UP = "text-emerald-600 dark:text-emerald-400";

export const money = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${Number(v).toFixed(2)}`);

export const toneOf = (v) => (v == null || v === 0 ? "text-text" : v > 0 ? UP : "text-brand");

export const pct = (v, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);