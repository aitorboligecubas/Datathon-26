import { useState } from "react";
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHmOperations, useOperations, type Operations } from "../lib/data";
import { AnimatedNumber, Card, Decision, ErrorBox, Kpi, Loading, SectionHeader } from "../components/ui";
import { TooltipBox, AreaGradient, RadialGauge } from "../components/charts";
import { C } from "../lib/theme";
import { eurCompact, hour, nf } from "../lib/format";

type Mode = "st" | "hm";
const WD = ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"];

export default function OpsToday({ mode }: { mode: Mode }) {
  const accent = mode === "hm" ? C.orange : C.upc;
  const st = useOperations();
  const hm = useHmOperations();
  const q = mode === "hm" ? hm : st;
  const [selHour, setSelHour] = useState<number | null>(null);
  if (q.isLoading || !q.data) return q.error ? <ErrorBox error={q.error} /> : <Loading />;
  const d: Operations = q.data;
  const selected = selHour != null ? d.today.find((t) => t.hour === selHour) ?? null : null;
  const s = d.status;
  const w = d.week;
  const now = new Date(s.timestamp);

  const modeColor = s.mode === "Carregant" ? C.blue : s.mode === "Descarregant" ? C.orange : C.muted;

  return (
    <div>
      <SectionHeader
        title="Monitoratge de la bateria"
        lead={`Com es veuria el monitoratge de la bateria de ${nf(d.battery.capacity_mwh)} MWh (±${nf(d.battery.power_kw)} kW): què fa, el pla del dia, el balanç de la setmana i els avisos. Pensat per a l'equip d'operació del campus.`}
      />

      <div className="mb-6 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/[0.08] px-4 py-2.5 text-[12px] leading-snug text-[#7a5200]">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" aria-hidden="true">
          <path d="M12 8v5m0 3h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span><b>Vista il·lustrativa · reproducció de dades històriques</b> (no és temps real): mostra com es veuria el monitoratge si la bateria estigués instal·lada.</span>
      </div>

      {/* Estat ARA */}
      <Card className="mb-6 p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <div className="flex flex-col items-center sm:w-64">
            <div className="mb-1 self-start text-[13px] font-medium text-ink-secondary">Càrrega de la bateria</div>
            <RadialGauge
              value={s.soc_pct}
              color={accent}
              center={<><AnimatedNumber value={s.soc_pct} />%</>}
              sub={`${nf(s.soc_mwh, 1)} de ${nf(d.battery.capacity_mwh)} MWh`}
            />
          </div>

          <div className="hidden w-px self-stretch bg-hair sm:block" />

          <div className="flex-1">
            <div className="text-[13px] font-medium text-ink-secondary">Ara mateix</div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold text-white" style={{ background: modeColor }}>
                <span className="inline-block h-2 w-2 rounded-full bg-white/90" />
                {s.mode}
                {s.power_kw > 0 && <span className="tabular">· {nf(s.power_kw)} kW</span>}
              </span>
              <span className="text-[13px] text-ink-secondary">
                {WD[s.weekday]}, {now.getDate()}/{now.getMonth() + 1} · {hour(s.hour)}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-3">
              <MiniStat value={`${nf(s.price_c, 1)}`} unit="cènt/kWh" label="preu ara" />
              <MiniStat value={`${nf(s.co2_g)}`} unit="g/kWh" label="CO₂ ara" />
              <MiniStat value={s.mode === "Repòs" ? "—" : `${nf(s.power_kw)}`} unit="kW" label="potència" />
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs de la setmana */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={`${nf(w.co2_saved_kg)} kg`} label="CO₂ evitat aquesta setmana" sub={`${w.days} dies`} tone="good" delay={0} />
        <Kpi value={eurCompact(w.eur_saved)} label="estalvi a la factura" sub="aquesta setmana" tone="good" delay={70} />
        <Kpi value={nf(w.cycles, 1)} label="cicles de bateria" sub="aquesta setmana" tone="accent" delay={140} />
        <Kpi value={w.infractions} label="infraccions" sub="0 = cap acció impossible" tone={w.infractions === 0 ? "good" : "default"} delay={210} />
      </div>

      {/* Pla d'avui */}
      <Card className="mt-6">
        <div className="px-5 pt-4">
          <h3 className="text-[15px] font-semibold text-ink">El pla d'avui</h3>
          <p className="mt-0.5 text-[13px] text-ink-secondary">
            Càrrega (blau) i descàrrega (taronja) hora a hora, i la càrrega de la bateria. La línia marca l'hora actual.
            <b> Clica una hora</b> per veure per què l'agent hi actua.
          </p>
        </div>
        {selected && (
          <div className="mx-5 mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl bg-plane px-4 py-3 text-[13px]">
            <div className="font-semibold text-ink">{hour(selected.hour)}</div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: selected.action_kw >= 0 ? C.blue : C.orange }} />
              <span className="text-ink">{selected.action_kw > 1 ? `Carrega ${nf(selected.action_kw)} kW` : selected.action_kw < -1 ? `Descarrega ${nf(-selected.action_kw)} kW` : "Repòs"}</span>
            </div>
            <div className="text-ink-secondary">pes <b className="text-ink">{nf(selected.weight, 2)}</b></div>
            <div className="text-ink-secondary">preu <b className="text-money">{nf(selected.price_c, 1)} c/kWh</b></div>
            <div className="text-ink-secondary">CO₂ <b className="text-co2">{nf(selected.co2_g)} g/kWh</b></div>
            <div className="w-full text-[12px] leading-snug text-ink-muted">
              {selected.action_kw > 1
                ? "El pes de l'hora és baix (energia neta i barata): convé carregar per fer-la servir més tard."
                : selected.action_kw < -1
                  ? "El pes de l'hora és alt (energia bruta i cara): convé descarregar per no comprar a la xarxa."
                  : "Ni prou barata per carregar ni prou cara per descarregar: la bateria espera."}
            </div>
          </div>
        )}
        <div className="px-2 sm:px-4">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={d.today} margin={{ top: 10, right: 12, bottom: 0, left: -12 }} syncId="ops">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis tickLine={false} axisLine={false} width={44} unit=" kW" />
              <ReferenceLine y={0} stroke={C.axis} />
              <ReferenceLine x={s.hour} stroke={C.ink} strokeDasharray="3 3" label={{ value: "ara", fontSize: 10, fill: C.ink, position: "top" }} />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox title={hour(Number(label))} rows={[{ label: "Acció", value: `${nf(Number(payload[0].value))} kW`, color: Number(payload[0].value) >= 0 ? C.blue : C.orange }]} />
                  ) : null
                }
              />
              <Bar dataKey="action_kw" radius={[2, 2, 0, 0]} isAnimationActive={false} onClick={(p: any) => setSelHour(p?.hour ?? null)} className="cursor-pointer">
                {d.today.map((p, i) => (
                  <Cell key={i} fill={p.action_kw >= 0 ? C.blue : C.orange} opacity={selHour === p.hour ? 1 : p.is_now ? 0.95 : 0.7} stroke={selHour === p.hour ? C.ink : undefined} strokeWidth={selHour === p.hour ? 1.5 : 0} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={140}>
            <ComposedChart data={d.today} margin={{ top: 4, right: 12, bottom: 4, left: -12 }} syncId="ops">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis domain={[0, d.battery.capacity_mwh]} tickLine={false} axisLine={false} width={44} unit=" MWh" />
              <ReferenceLine x={s.hour} stroke={C.ink} strokeDasharray="3 3" />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox title={hour(Number(label))} rows={[{ label: "Càrrega", value: `${nf(Number(payload[0].value), 2)} MWh`, color: accent }]} />
                  ) : null
                }
              />
              <AreaGradient id="opsSoc" color={accent} />
              <Area type="monotone" dataKey="soc_mwh" stroke={accent} strokeWidth={2.5} fill="url(#opsSoc)" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Alertes */}
      <Card className="mt-6 p-5">
        <h3 className="text-[15px] font-semibold text-ink">Avisos i estat del sistema</h3>
        <div className="mt-3 space-y-2">
          {d.alerts.map((a, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg bg-plane px-3 py-2.5">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full" style={{ background: a.level === "good" ? "rgba(12,163,12,0.12)" : "rgba(250,178,25,0.18)" }}>
                {a.level === "good" ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke={C.good} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M12 8v5M12 16h.01" stroke="#b7791f" strokeWidth="2.5" strokeLinecap="round" /></svg>
                )}
              </span>
              <div>
                <div className="text-[13px] font-semibold text-ink">{a.label}</div>
                <div className="text-[12px] leading-snug text-ink-secondary">{a.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="mt-6">
        <Decision>
          La bateria opera sola i segura: carrega a les hores netes i barates, descarrega als pics i no comet cap infracció.
          L'equip d'operació només ha de vigilar els <b>avisos</b> (sensors, excedent, previsió) i confirmar que l'estalvi
          setmanal es manté.
        </Decision>
      </div>
    </div>
  );
}

function MiniStat({ value, unit, label }: { value: string; unit: string; label: string }) {
  return (
    <div className="rounded-lg bg-plane px-3 py-2">
      <div className="text-[18px] font-semibold leading-none tabular text-ink">
        {value}
        {unit && <span className="ml-1 text-[11px] font-normal text-ink-muted">{unit}</span>}
      </div>
      <div className="mt-1 text-[11px] leading-tight text-ink-secondary">{label}</div>
    </div>
  );
}
