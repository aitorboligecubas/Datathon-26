import { useEffect, useRef, useState, type ReactNode } from "react";
import { nf } from "../lib/format";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-black/[0.06] bg-white shadow-soft transition-shadow duration-200 hover:shadow-lift ${className}`}>
      {children}
    </div>
  );
}

/** Compta amunt fins a `target` quan entra a la vista (cubic ease-out). */
export function useCountUp(target: number, duration = 850): number {
  const [v, setV] = useState(0);
  const prefersReduced = useRef(typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    if (prefersReduced.current) {
      setV(target);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - t0) / duration, 1);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return v;
}

/** True poc després de muntar-se: per animar amplades de barres de 0 al valor. */
export function useGrow(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const r = requestAnimationFrame(() => setOn(true));
    return () => cancelAnimationFrame(r);
  }, []);
  return on;
}

/** Número que compta amunt, amb format català. */
export function AnimatedNumber({ value, decimals = 0, prefix = "", suffix = "" }: { value: number; decimals?: number; prefix?: string; suffix?: string }) {
  const v = useCountUp(value);
  return <>{prefix}{nf(v, decimals)}{suffix}</>;
}

/** Tarjeta de gráfica: título + subtítulo + la propia gráfica + la CONCLUSIÓN. */
export function ChartCard({
  title,
  subtitle,
  children,
  conclusion,
  conclusionTone = "money",
  source,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  conclusion?: ReactNode;
  conclusionTone?: "co2" | "money";
  source?: string;
  className?: string;
}) {
  const isCo2 = conclusionTone === "co2";
  const boxCls = isCo2 ? "bg-co2/[0.08]" : "bg-upc/[0.06]";
  const txtCls = isCo2 ? "text-co2" : "text-upc";
  return (
    <Card className={`group/card flex flex-col ${className}`}>
      <div className="px-6 pt-5">
        <h3 className="text-[16px] font-semibold tracking-tight text-ink">{title}</h3>
        {subtitle && <p className="mt-1 text-[13px] leading-snug text-ink-secondary">{subtitle}</p>}
      </div>
      <div className="px-3 pt-4 sm:px-5">{children}</div>
      {conclusion && (
        <div className={`mx-5 mb-4 mt-2 flex items-start gap-2 rounded-xl px-3.5 py-2.5 text-[13px] leading-snug text-ink-secondary ${boxCls}`}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" className={`mt-0.5 shrink-0 ${txtCls}`} aria-hidden="true">
            <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.3 1 2.1V16h6v-.4c0-.8.4-1.5 1-2.1A6 6 0 0 0 12 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span><span className={`font-semibold ${txtCls}`}>Conclusió. </span>{conclusion}</span>
        </div>
      )}
      {source && <p className="px-6 pb-4 text-[11px] text-ink-muted">{source}</p>}
    </Card>
  );
}

type Tone = "default" | "good" | "accent" | "co2" | "money" | "solar";
const TONE_CHIP: Record<Tone, string> = {
  co2: "bg-co2/10 text-co2",
  money: "bg-money/10 text-money",
  solar: "bg-solar/15 text-[#b5790a]",
  good: "bg-good/10 text-good",
  accent: "bg-upc/10 text-upc",
  default: "bg-black/[0.05] text-ink-muted",
};
const TONE_ICON: Record<Tone, string> = {
  co2: "M4 20c8 2 16-4 16-14 0 0-10-2-14 4-2 3-2 7-2 10zM5 19c2-6 6-9 10-11", // fulla
  money: "M15.5 7a5 5 0 1 0 0 10M6 10.5h7M6 13.5h7", // euro
  solar: "M12 4v2M12 18v2M4 12H2M22 12h-2M6 6 4.6 4.6M19.4 19.4 18 18M18 6l1.4-1.4M4.6 19.4 6 18M12 8.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7", // sol
  good: "M20 6 9 17l-5-5", // check
  accent: "M13 2 3 14h7l-1 8 10-12h-7z", // llamp
  default: "M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
};

/** Indicador grande (KPI / stat tile) estil SaaS: número gran + chip d'icona. */
export function Kpi({
  value,
  label,
  sub,
  tone = "default",
  delay = 0,
  onClick,
}: {
  value: ReactNode;
  label: string;
  sub?: ReactNode;
  tone?: Tone;
  delay?: number;
  onClick?: () => void;
}) {
  const valueColor =
    tone === "good" ? "text-good"
    : tone === "co2" ? "text-co2"
    : tone === "money" ? "text-money"
    : tone === "solar" ? "text-[#b5790a]"
    : tone === "accent" ? "text-upc"
    : "text-ink";
  return (
    <div
      onClick={onClick}
      style={{ animationDelay: `${delay}ms` }}
      className={`animate-pop rounded-2xl border border-black/[0.06] bg-white px-5 py-4 shadow-soft transition duration-200 hover:-translate-y-1 hover:shadow-lift ${onClick ? "cursor-pointer" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className={`text-[34px] font-bold leading-none tracking-tight tabular ${valueColor}`}>{value}</div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${TONE_CHIP[tone]}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d={TONE_ICON[tone]} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </div>
      <div className="mt-3 flex items-center gap-1 text-[13px] font-medium text-ink">
        {label}
        {onClick && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="text-ink-muted" aria-hidden="true">
            <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      {sub && <div className="mt-0.5 text-[12px] leading-snug text-ink-secondary">{sub}</div>}
    </div>
  );
}

/** Franja de decisión: lo que el gráfico permite decidir. */
export function Decision({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-upc/20 bg-upc/[0.06] p-4 shadow-soft">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-upc/15 text-upc">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.3 1 2.1V16h6v-.4c0-.8.4-1.5 1-2.1A6 6 0 0 0 12 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <div>
        <div className="mb-0.5 text-[12px] font-semibold uppercase tracking-wide text-upc">Decisió que fonamenta</div>
        <div className="text-[14px] leading-snug text-ink">{children}</div>
      </div>
    </div>
  );
}

/** Capçalera personalitzada per a qui obre el dashboard (salutació gran + subtítol curt). */
export function WelcomeHeader({
  name,
  role,
  subtitle,
  accent = "#007bc0",
}: {
  name: string;
  role: string;
  subtitle: string;
  accent?: string;
}) {
  void name;
  return (
    <div className="animate-pop mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-[30px] font-bold leading-tight tracking-tight text-ink sm:text-[38px]">Benvingut/da</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">{subtitle}</p>
      </div>
      <div className="flex items-center gap-3 rounded-2xl border border-black/[0.06] bg-white px-3 py-2 shadow-soft">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-full text-white"
          style={{ background: `linear-gradient(135deg, ${accent}, ${accent}b3)` }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20a7 7 0 0 1 14 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <div className="pr-1 text-[12px] font-semibold leading-tight text-ink">{role}</div>
      </div>
    </div>
  );
}

/** Capçalera amb imatge real del campus (foto + degradat + títol a sobre). */
export function HeroBanner({
  image,
  title,
  lead,
  badge,
  accent = "#007bc0",
  credit,
}: {
  image: string;
  title: string;
  lead: string;
  badge?: string;
  accent?: string;
  credit?: string;
}) {
  const src = `${import.meta.env.BASE_URL}${image}`;
  return (
    <div className="animate-pop relative mb-6 overflow-hidden rounded-2xl border border-black/[0.06] shadow-soft">
      <img src={src} alt="Campus Nord de la UPC" className="h-44 w-full object-cover sm:h-56" loading="eager" />
      <div className="absolute inset-0" style={{ background: "linear-gradient(90deg, rgba(10,12,16,0.82) 0%, rgba(10,12,16,0.55) 45%, rgba(10,12,16,0.12) 100%)" }} />
      <div className="absolute inset-0 flex flex-col justify-end p-6">
        {badge && (
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-white">
            <span className="rounded-full px-2.5 py-1 shadow-sm" style={{ background: accent }}>{badge}</span>
          </div>
        )}
        <h2 className="max-w-2xl text-[26px] font-bold leading-tight text-white drop-shadow-sm">{title}</h2>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-snug text-white/85">{lead}</p>
      </div>
      {credit && <div className="absolute bottom-1 right-2 text-[9px] text-white/55">{credit}</div>}
    </div>
  );
}

const DAY_NAMES = ["Dilluns", "Dimarts", "Dimecres", "Dijous", "Divendres", "Dissabte", "Diumenge"];

/** Desplegable per triar dia de la setmana (o tota la setmana). */
export function DaySelect({ day, setDay, accent = "#007bc0" }: { day: number | null; setDay: (d: number | null) => void; accent?: string }) {
  return (
    <div className="relative no-print">
      <select
        value={day == null ? "all" : String(day)}
        onChange={(e) => setDay(e.target.value === "all" ? null : Number(e.target.value))}
        className="cursor-pointer appearance-none rounded-lg border border-black/10 bg-white py-1.5 pl-3 pr-9 text-[13px] font-medium text-ink shadow-soft transition-colors hover:border-black/20 focus:outline-none"
      >
        <option value="all">Tota la setmana</option>
        {DAY_NAMES.map((d, i) => (
          <option key={i} value={i}>{d}</option>
        ))}
      </select>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2" style={{ color: accent }} aria-hidden="true">
        <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

export function SectionHeader({ title, lead }: { title: string; lead: string }) {
  return (
    <div className="mb-5 max-w-3xl">
      <h2 className="text-[26px] font-bold tracking-tight text-ink">{title}</h2>
      <p className="mt-1.5 text-[15px] leading-relaxed text-ink-secondary">{lead}</p>
    </div>
  );
}

export function Loading() {
  return (
    <div className="flex h-64 items-center justify-center text-ink-muted">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-hair border-t-upc" />
      <span className="ml-3 text-sm">Carregant dades…</span>
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="rounded-2xl border border-critical/30 bg-critical/5 p-4 text-sm text-ink">
      No s'han pogut carregar les dades: {String((error as Error)?.message ?? error)}
    </div>
  );
}

export function Pill({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "good" | "warn" }) {
  const cls =
    tone === "good"
      ? "bg-good/10 text-good"
      : tone === "warn"
        ? "bg-warning/15 text-[#8a5a00]"
        : "bg-black/[0.05] text-ink-secondary";
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium ${cls}`}>{children}</span>;
}
