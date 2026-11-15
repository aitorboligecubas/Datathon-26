// Paleta validada (dataviz skill) — coincide con las figuras de P2 (analysis/figs).
export const C = {
  surface: "#fcfcfb",
  plane: "#f9f9f7",
  ink: "#0b0b0b",
  inkSecondary: "#52514e",
  muted: "#898781",
  hair: "#e1e0d9",
  axis: "#c3c2b7",
  // categóricas (orden fijo)
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  magenta: "#e87ba4",
  violet: "#6250d6",
  red: "#e34948",
  // estado
  good: "#0ca30c",
  warning: "#fab219",
  critical: "#d03b3b",
  upc: "#007bc0", // blau del logo UPC = marca + diners
  // SEMÀNTICA PER MÈTRICA (color = significat)
  co2: "#1f8f56", // verd = CO₂ / emissions
  money: "#007bc0", // blau UPC = diners / preu / cost
  solar: "#f5a623", // ambre = solar
  load: "#5b6b7a", // slate neutre = consum del campus
} as const;

// Rampa blava (UPC) per a mapes de calor de diners/preu.
export const BLUE_RAMP = [
  "#d6ebf7", "#a9d4ee", "#74b8e2", "#3f97d2", "#1b84c7", "#007bc0", "#0a5f93", "#0a4a73",
];

// Rampa verda per a mapes de calor de CO₂ (sequential, clar -> fosc).
export const GREEN_RAMP = [
  "#e4f6ec", "#c2e9d3", "#92d8b0", "#5cc68c", "#2faa6a", "#1f8f56", "#166b41", "#0e4d2e",
];

// Rampa ambre per a solar.
export const SOLAR_RAMP = [
  "#fff3d1", "#ffe39a", "#ffcf5c", "#f7b32b", "#ec9a08", "#c87d06", "#9a5f06", "#6e4405",
];

// Rampa secuencial naranja (acció: descàrrega).
export const ORANGE_RAMP = [
  "#fdeee6", "#fbd9c6", "#f7b393", "#f28a5c", "#eb6834", "#cf5120", "#a53e18", "#78290f",
];

// Rampa "de calor" semántica (ámbar -> naranja -> rojo) para el mapa de consumo del campus.
// Calor semántico = excepción permitida a "un solo tono", siempre con leyenda de escala.
export const HEAT_RAMP = [
  "#fcefc7", "#fbdd8a", "#f6b64c", "#ef8b2c", "#e3611f", "#cc3a1f", "#9e1f1f",
];

// Interpola una rampa (t en 0..1) devolviendo un color hex.
export function rampColor(ramp: string[], t: number): string {
  const x = Math.max(0, Math.min(1, t)) * (ramp.length - 1);
  const i = Math.floor(x);
  const f = x - i;
  if (i >= ramp.length - 1) return ramp[ramp.length - 1];
  const a = hexToRgb(ramp[i]);
  const b = hexToRgb(ramp[i + 1]);
  const mix = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `#${mix.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

function hexToRgb(hex: string): number[] {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}

// Color de texto legible sobre un fondo dado (para celdas del heatmap).
export function readableText(bg: string): string {
  const [r, g, b] = hexToRgb(bg);
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return lum > 0.6 ? C.ink : "#ffffff";
}
