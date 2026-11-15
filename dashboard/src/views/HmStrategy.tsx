import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHmStrategies } from "../lib/data";
import { Card, DaySelect, Decision, ErrorBox, Loading, Pill, SectionHeader } from "../components/ui";
import { Legend, TooltipBox, AreaGradient } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf, WEEKDAYS } from "../lib/format";

export default function HmStrategy() {
  const { data, isLoading, error } = useHmStrategies();
  const [day, setDay] = useState<number | null>(null);
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;

  const v8 = data.ladder.find((l) => l.key === "v7")!;

  const pts = data.week.points;
  const filtered = day == null ? pts : pts.filter((p) => p.weekday === day);
  const week = filtered.map((p, i) => ({
    idx: i, ts: p.timestamp, hour: p.hour, weekday: p.weekday, weight: p.weight, soc: p.soc_mwh,
    charge: p.action_kw > 1 ? p.weight : null, discharge: p.action_kw < -1 ? p.weight : null,
    action: p.action_kw, pv: p.pv_kw, load: p.load_kw,
  }));
  const dayTicks = day == null ? week.filter((w) => w.hour === 0).map((w) => w.idx) : week.filter((w) => w.hour % 6 === 0).map((w) => w.idx);
  const tickLabel = (idx: number) => {
    const w = week[idx];
    if (!w) return "";
    return day == null ? WEEKDAYS[w.weekday] : hour(w.hour);
  };

  return (
    <div>
      <SectionHeader
        title="Com gestiona la bateria ampliada"
        lead="El mateix GPS (planifica 24 h, executa 1 h) amb tres peces noves: previsió de preu/CO₂, previsió de solar/consum i un marge de seguretat. Aquí es veu l'agent gestionant la bateria de 6 MWh hora a hora."
      />

      <Card className="mt-6">
        <div className="flex flex-col gap-2 px-5 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-[15px] font-semibold text-ink">L'agent en acció: una setmana de juliol</h3>
            <p className="mt-0.5 text-[13px] text-ink-secondary">
              A dalt, el «pes» de cada hora (1 = mitjana) amb les hores de càrrega (blau) i descàrrega (taronja). A sota, la càrrega
              de la bateria de 6 MWh: carrega a migdia (amb l'excedent solar) i descarrega al vespre.
            </p>
          </div>
          <DaySelect day={day} setDay={setDay} accent={C.orange} />
        </div>
        <Legend items={[{ label: "Pes de l'hora", color: C.muted, shape: "line" }, { label: "Carrega", color: C.blue }, { label: "Descarrega", color: C.orange }]} />
        <div className="px-2 sm:px-4">
          <ResponsiveContainer width="100%" height={170}>
            <ComposedChart data={week} margin={{ top: 6, right: 12, bottom: 0, left: -10 }} syncId="hmweek">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="idx" type="number" domain={["dataMin", "dataMax"]} ticks={dayTicks} tickFormatter={tickLabel} tickLine={false} />
              <YAxis domain={[0.4, "auto"]} tickLine={false} axisLine={false} width={34} />
              <ReferenceLine y={1} stroke={C.axis} />
              <Tooltip content={<WeekTip week={week} />} />
              <Area type="monotone" dataKey="charge" baseValue={1} stroke="none" fill={C.blue} fillOpacity={0.3} isAnimationActive={false} connectNulls={false} />
              <Area type="monotone" dataKey="discharge" baseValue={1} stroke="none" fill={C.orange} fillOpacity={0.4} isAnimationActive={false} connectNulls={false} />
              <Line type="monotone" dataKey="weight" stroke={C.muted} strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <ResponsiveContainer width="100%" height={150}>
            <ComposedChart data={week} margin={{ top: 4, right: 12, bottom: 4, left: -10 }} syncId="hmweek">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="idx" type="number" domain={["dataMin", "dataMax"]} ticks={dayTicks} tickFormatter={tickLabel} tickLine={false} />
              <YAxis domain={[0, 6]} ticks={[0, 3, 6]} tickLine={false} axisLine={false} width={34} unit=" MWh" />
              <Tooltip content={<WeekTip week={week} />} />
              <AreaGradient id="hmSoc" color={C.orange} />
              <Area type="monotone" dataKey="soc" stroke={C.orange} strokeWidth={2.5} fill="url(#hmSoc)" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mx-5 mb-4 mt-2 rounded-lg border-l-[3px] border-orange bg-orange/[0.06] px-3 py-2 text-[13px] leading-snug text-ink-secondary">
          <span className="font-semibold text-orange">Conclusió. </span>
          La bateria fa cicles més grans (6 MWh): s'omple a migdia amb l'excedent solar barat i net, i es buida al pic del vespre.
        </div>
      </Card>

      <div className="mt-6">
        <Decision>
          Mantenir el mateix planificador (MPC + LP) i concentrar la millora en les <b>previsions</b> i el <b>marge de seguretat</b>:
          és el que fa que la bateria gran aprofiti l'excedent sense vessar energia descarregant a cegues.
        </Decision>
        <div className="mt-2 flex items-center justify-center gap-2 text-[12px] text-ink-muted">
          <Pill tone="good">{v8.infr} infraccions</Pill>
          <span>·</span>
          <span>gestió autònoma, hora a hora</span>
        </div>
      </div>
    </div>
  );
}

function WeekTip({ week, active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = week[payload[0].payload.idx];
  if (!p) return null;
  const d = new Date(p.ts);
  return (
    <TooltipBox
      title={`${WEEKDAYS[p.weekday]} ${d.getDate()}, ${hour(p.hour)}`}
      rows={[
        { label: "Pes", value: nf(p.weight, 2), color: C.muted },
        { label: "Càrrega", value: `${nf(p.soc, 2)} MWh`, color: C.orange },
        { label: "Solar", value: `${nf(p.pv)} kW`, color: C.yellow },
        { label: "Acció", value: `${p.action > 0 ? "+" : ""}${nf(p.action)} kW`, color: p.action >= 0 ? C.blue : C.orange },
      ]}
    />
  );
}

