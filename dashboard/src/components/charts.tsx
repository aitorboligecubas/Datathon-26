import type { ReactNode } from "react";
import { C, rampColor, readableText } from "../lib/theme";

/** Tooltip con estilo coherente para Recharts. `rows` pinta nombre·valor con su color. */
export function TooltipBox({
  title,
  rows,
}: {
  title?: ReactNode;
  rows: { label: string; value: ReactNode; color?: string }[];
}) {
  return (
    <div className="rounded-lg border border-black/10 bg-surface/95 px-3 py-2 text-[12px] shadow-card backdrop-blur">
      {title != null && <div className="mb-1 font-semibold text-ink">{title}</div>}
      <div className="space-y-0.5">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-ink-secondary">
              {r.color && <span className="inline-block h-2 w-2 rounded-sm" style={{ background: r.color }} />}
              {r.label}
            </span>
            <span className="tabular font-medium text-ink">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Leyenda horizontal en forma de "pills" suaves. */
export function Legend({ items }: { items: { label: string; color: string; shape?: "line" | "dot" | "box" }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-2 px-3 pb-1 text-[12px] font-medium text-ink-secondary">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5 rounded-full bg-black/[0.035] px-2.5 py-1">
          {it.shape === "line" ? (
            <span className="inline-block h-[3px] w-4 rounded-full" style={{ background: it.color }} />
          ) : (
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: it.color }} />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}

/** Defs de degradat vertical per a àrees (color -> transparent). Usar fill={`url(#id)`}. */
export function AreaGradient({ id, color, top = 0.28, bottom = 0.02 }: { id: string; color: string; top?: number; bottom?: number }) {
  return (
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity={top} />
        <stop offset="100%" stopColor={color} stopOpacity={bottom} />
      </linearGradient>
    </defs>
  );
}

/** Indicador radial de «pètals» (arc de segments arrodonits) amb el valor al centre. */
export function RadialGauge({
  value,
  max = 100,
  color,
  size = 176,
  segments = 44,
  center,
  sub,
}: {
  value: number;
  max?: number;
  color: string;
  size?: number;
  segments?: number;
  center: ReactNode;
  sub?: ReactNode;
}) {
  const frac = Math.max(0, Math.min(1, value / max));
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 5;
  const rInner = rOuter - 15;
  const START = 140; // graus; 0 = dreta, positiu cap avall
  const SWEEP = 260; // forat a baix
  const lit = Math.round(frac * (segments - 1));
  const seg = [];
  for (let i = 0; i < segments; i++) {
    const a = ((START + (SWEEP * i) / (segments - 1)) * Math.PI) / 180;
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    seg.push(
      <line
        key={i}
        x1={cx + rInner * cos}
        y1={cy + rInner * sin}
        x2={cx + rOuter * cos}
        y2={cy + rOuter * sin}
        stroke={i <= lit ? color : "#e7ebf1"}
        strokeWidth={4.5}
        strokeLinecap="round"
      />,
    );
  }
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden="true">
        {seg}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-[34px] font-bold leading-none tabular" style={{ color }}>{center}</div>
        {sub && <div className="mt-1 max-w-[70%] text-center text-[11px] leading-tight text-ink-secondary">{sub}</div>}
      </div>
    </div>
  );
}

/** Mapa de calor mes × hora (sequential, una sola tonalidad). */
export function Heatmap({
  data,
  ramp,
  unit,
  format = (v) => String(Math.round(v)),
}: {
  data: { months: string[]; hours: number[]; values: number[][] };
  ramp: string[];
  unit: string;
  format?: (v: number) => string;
}) {
  const flat = data.values.flat();
  const min = Math.min(...flat);
  const max = Math.max(...flat);
  const norm = (v: number) => (max === min ? 0.5 : (v - min) / (max - min));
  return (
    <div className="px-3 pb-2">
      <div className="overflow-x-auto">
        <div className="min-w-[520px]">
          {/* Cabecera de horas */}
          <div className="flex pl-9">
            {data.hours.map((h) => (
              <div key={h} className="flex-1 text-center text-[9px] text-ink-muted">
                {h % 3 === 0 ? h : ""}
              </div>
            ))}
          </div>
          {data.months.map((m, r) => (
            <div key={m} className="flex items-stretch">
              <div className="flex w-9 items-center justify-end pr-1.5 text-[10px] font-medium text-ink-secondary">
                {m}
              </div>
              {data.values[r].map((v, c) => {
                const bg = rampColor(ramp, norm(v));
                return (
                  <div
                    key={c}
                    className="group relative flex-1"
                    style={{ aspectRatio: "1.1", background: bg }}
                    title={`${m} · ${String(data.hours[c]).padStart(2, "0")}:00 — ${format(v)} ${unit}`}
                  >
                    <span
                      className="pointer-events-none absolute inset-0 hidden items-center justify-center text-[9px] font-semibold group-hover:flex"
                      style={{ color: readableText(bg) }}
                    >
                      {format(v)}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      {/* Escala */}
      <div className="mt-2 flex items-center gap-2 pl-9 text-[10px] text-ink-muted">
        <span className="tabular">{format(min)}</span>
        <span
          className="h-2 w-28 rounded-full"
          style={{ background: `linear-gradient(90deg, ${ramp[1]}, ${ramp[ramp.length - 2]})` }}
        />
        <span className="tabular">{format(max)}</span>
        <span>{unit}</span>
      </div>
    </div>
  );
}

export { C };
