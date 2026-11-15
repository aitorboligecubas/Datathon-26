// Formato de números en catalán (coma decimal, punt de miler).
const ca = "ca-ES";

export const nf = (x: number, dec = 0) =>
  new Intl.NumberFormat(ca, { minimumFractionDigits: dec, maximumFractionDigits: dec }).format(x);

export const pct = (x: number, dec = 1) => `${nf(x, dec)} %`;

export const eur = (x: number, dec = 0) =>
  new Intl.NumberFormat(ca, { style: "currency", currency: "EUR", maximumFractionDigits: dec }).format(x);

// Euros compactos: 92.421 € -> "92 k€", 183.593 € -> "0,18 M€"
export function eurCompact(x: number): string {
  if (Math.abs(x) >= 1_000_000) return `${nf(x / 1_000_000, 2)} M€`;
  if (Math.abs(x) >= 1_000) return `${nf(x / 1_000, 0)} k€`;
  return eur(x);
}

export const hour = (h: number) => `${String(h).padStart(2, "0")}:00`;

export const WEEKDAYS = ["dl", "dt", "dc", "dj", "dv", "ds", "dg"];
