import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useStrategies } from "../lib/data";
import { Card, DaySelect, Decision, ErrorBox, Loading, Pill, SectionHeader } from "../components/ui";
import { Legend, TooltipBox, AreaGradient } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf, WEEKDAYS } from "../lib/format";

export default function Strategy() {
  const { data, isLoading, error } = useStrategies();
  const [day, setDay] = useState<number | null>(null);
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;

  const mpc = data.comparison.find((c) => c.key === "mpc")!;

  const pts = data.week.points;
  const filtered = day == null ? pts : pts.filter((p) => p.weekday === day);
  const week = filtered.map((p, i) => ({
    idx: i,
    ts: p.timestamp,
    hour: p.hour,
    weekday: p.weekday,
    weight: p.weight,
    soc: p.soc_mwh,
    charge: p.action_kw > 1 ? p.weight : null,
    discharge: p.action_kw < -1 ? p.weight : null,
    action: p.action_kw,
  }));
  const dayTicks = day == null ? week.filter((w) => w.hour === 0).map((w) => w.idx) : week.filter((w) => w.hour % 6 === 0).map((w) => w.idx);
  const tickLabel = (idx: number) => {
    const w = week[idx];
    if (!w) return "";
    return day == null ? `${WEEKDAYS[w.weekday]}` : hour(w.hour);
  };

  return (
    <div>
      <SectionHeader
        title="Com gestiona la bateria"
        lead="L'agent fa MPC: cada hora replanifica les 24 h següents i executa només el primer pas. Aquí es veu actuant hora a hora — carrega quan la xarxa és neta i barata, descarrega quan és bruta i cara, sense cap regla escrita a mà."
      />

      {/* Semana tipo */}
      <Card className="mt-6">
        <div className="flex flex-col gap-2 px-5 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-[15px] font-semibold text-ink">L'agent en acció: una setmana de juliol</h3>
            <p className="mt-0.5 text-[13px] text-ink-secondary">
              A dalt, el «pes» de cada hora (1 = hora mitjana). A sota, la càrrega de la bateria. Carrega a les valls i
              descarrega als pics, cada dia, sense regles escrites a mà.
            </p>
          </div>
          <DaySelect day={day} setDay={setDay} accent={C.upc} />
        </div>
        <Legend
          items={[
            { label: "Pes de l'hora", color: C.muted, shape: "line" },
            { label: "L'agent carrega", color: C.blue },
            { label: "L'agent descarrega", color: C.orange },
          ]}
        />
        <div className="px-2 sm:px-4">
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={week} margin={{ top: 6, right: 12, bottom: 0, left: -10 }} syncId="week">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="idx" type="number" domain={["dataMin", "dataMax"]} ticks={dayTicks} tickFormatter={tickLabel} tickLine={false} />
              <YAxis domain={[0.4, "auto"]} tickLine={false} axisLine={false} width={34} />
              <ReferenceLine y={1} stroke={C.axis} />
              <Tooltip content={<WeekTooltip week={week} />} />
              <Area type="monotone" dataKey="charge" baseValue={1} stroke="none" fill={C.blue} fillOpacity={0.3} isAnimationActive={false} connectNulls={false} />
              <Area type="monotone" dataKey="discharge" baseValue={1} stroke="none" fill={C.orange} fillOpacity={0.4} isAnimationActive={false} connectNulls={false} />
              <Line type="monotone" dataKey="weight" stroke={C.muted} strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={week} margin={{ top: 4, right: 12, bottom: 4, left: -10 }} syncId="week">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="idx" type="number" domain={["dataMin", "dataMax"]} ticks={dayTicks} tickFormatter={tickLabel} tickLine={false} />
              <YAxis domain={[0, 2]} ticks={[0, 1, 2]} tickLine={false} axisLine={false} width={34} unit=" MWh" />
              <Tooltip content={<WeekTooltip week={week} />} />
              <AreaGradient id="stSoc" color={C.upc} />
              <Area type="monotone" dataKey="soc" stroke={C.upc} strokeWidth={2.5} fill="url(#stSoc)" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mx-5 mb-4 mt-2 rounded-lg border-l-[3px] border-upc bg-upc/[0.05] px-3 py-2 text-[13px] leading-snug text-ink-secondary">
          <span className="font-semibold text-upc">Conclusió. </span>
          El comportament emergeix del LP: omple quan el pes és baix, buida quan és alt. Cap hora programada a mà.
        </div>
      </Card>

      <div className="mt-6">
        <Decision>
          La bateria ja treu gairebé tot el que permet la seva mida. Per guanyar més estalvi, l'única palanca que queda és{" "}
          <b>física</b> — ampliar la bateria. Això ho quantifica la pàgina següent.
        </Decision>
        <div className="mt-2 flex items-center justify-center gap-2 text-[12px] text-ink-muted">
          <Pill tone="good">{mpc.infractions} infraccions</Pill>
          <span>·</span>
          <span>gestió autònoma, hora a hora</span>
        </div>
      </div>
    </div>
  );
}

function WeekTooltip({ week, active, payload }: any) {
  if (!active || !payload?.length) return null;
  const idx = payload[0].payload.idx as number;
  const p = week[idx];
  if (!p) return null;
  const d = new Date(p.ts);
  return (
    <TooltipBox
      title={`${WEEKDAYS[p.weekday]} ${d.getDate()}, ${hour(p.hour)}`}
      rows={[
        { label: "Pes", value: nf(p.weight, 2), color: C.muted },
        { label: "Càrrega", value: `${nf(p.soc, 2)} MWh`, color: C.blue },
        { label: "Acció", value: `${p.action > 0 ? "+" : ""}${nf(p.action)} kW`, color: p.action >= 0 ? C.blue : C.orange },
      ]}
    />
  );
}


