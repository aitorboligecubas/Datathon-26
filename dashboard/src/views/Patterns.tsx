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
import { useState } from "react";
import { usePatterns } from "../lib/data";
import { ChartCard, Decision, ErrorBox, Loading, SectionHeader } from "../components/ui";
import { Heatmap, Legend, TooltipBox } from "../components/charts";
import { C, GREEN_RAMP, BLUE_RAMP } from "../lib/theme";
import { hour, nf } from "../lib/format";

export default function Patterns() {
  const { data: p, isLoading, error } = usePatterns();
  const [metric, setMetric] = useState<"co2" | "price">("co2");
  if (isLoading || !p) return error ? <ErrorBox error={error} /> : <Loading />;
  const s = p.summary;
  const isCo2 = metric === "co2";

  const co2Data = p.hourly.map((h) => ({ hour: h.hour, mean: h.co2_g, base: h.co2_p25, band: h.co2_p75 - h.co2_p25 }));
  const priceData = p.hourly.map((h) => ({ hour: h.hour, mean: h.price_c, base: h.price_p25, band: h.price_p75 - h.price_p25 }));
  const conflict = p.conflict_hourly;

  return (
    <div>
      <SectionHeader
        title="Quan és bruta i cara la xarxa?"
        lead="Si la bateria ha de moure energia en el temps, primer cal saber cap a on. Aquestes vistes mostren el patró horari i mensual del CO₂ i del preu, i si tots dos assenyalen les mateixes hores."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="CO₂ de la xarxa per hora del dia"
          subtitle="Mitjana de l'any; banda = meitat central dels dies (p25–p75)."
          conclusionTone="co2"
          conclusion={
            <>
              La xarxa és més neta a <b>les {s.co2_best_hour} h</b> ({nf(s.co2_best_val)} g/kWh) i més bruta a{" "}
              <b>les {s.co2_worst_hour} h</b> ({nf(s.co2_worst_val)} g/kWh): <b>{nf(s.co2_ratio, 2)}×</b> més.
            </>
          }
          source={`${nf(s.n_hours)} h de dades de CO₂ (tot l'històric, novembre inclòs).`}
        >
          <Legend items={[{ label: "Mitjana horària", color: C.co2, shape: "line" }, { label: "p25–p75", color: "#c2e9d3" }]} />
          <BandChart data={co2Data} color={C.co2} bandColor={C.co2} unit="g/kWh" best={s.co2_best_hour} worst={s.co2_worst_hour} />
        </ChartCard>

        <ChartCard
          title="Preu PVPC per hora del dia"
          subtitle="Mitjana de l'any; banda = meitat central dels dies (p25–p75)."
          conclusion={
            <>
              El preu va de <b>{nf(s.price_best_val, 1)} cèntims a les {s.price_best_hour} h</b> a{" "}
              <b>{nf(s.price_worst_val, 1)} a les {s.price_worst_hour} h</b>: <b>{nf(s.price_ratio, 2)}×</b> més car al vespre.
            </>
          }
          source="Preu PVPC horari de tot l'històric."
        >
          <Legend items={[{ label: "Mitjana horària", color: C.money, shape: "line" }, { label: "p25–p75", color: "#a9d4ee" }]} />
          <BandChart data={priceData} color={C.money} bandColor={C.money} unit="cènt./kWh" best={s.price_best_hour} worst={s.price_worst_hour} />
        </ChartCard>
      </div>

      <div className="mt-6">
        <ChartCard
          title={`${isCo2 ? "CO₂ de la xarxa (g/kWh)" : "Preu PVPC (cènt./kWh)"}: mes × hora`}
          subtitle="Com més fosc, pitjor per comprar. L'ordre és el curs: de setembre a agost. Tria la mètrica."
          conclusionTone={isCo2 ? "co2" : "money"}
          conclusion={
            isCo2 ? (
              <>
                El patró es repeteix tot l'any però és molt més marcat a l'estiu. L'agost és el mes que més aporta a
                l'estalvi; el febrer és net gairebé a totes hores.
              </>
            ) : (
              <>El preu també es concentra al vespre i puja a l'estiu: el patró s'assembla al del CO₂, però no és idèntic.</>
            )
          }
        >
          <div className="mb-1 flex gap-1.5 px-3">
            {(["co2", "price"] as const).map((m) => {
              const on = metric === m;
              const col = m === "co2" ? C.co2 : C.money;
              return (
                <button
                  key={m}
                  onClick={() => setMetric(m)}
                  className={`rounded-lg px-3 py-1 text-[12px] font-semibold transition-colors ${on ? "text-white" : "bg-black/[0.05] text-ink-secondary hover:bg-black/[0.08]"}`}
                  style={on ? { background: col } : undefined}
                >
                  {m === "co2" ? "CO₂" : "Preu"}
                </button>
              );
            })}
          </div>
          <Heatmap data={isCo2 ? p.heatmap_co2 : p.heatmap_price} ramp={isCo2 ? GREEN_RAMP : BLUE_RAMP} unit={isCo2 ? "g/kWh" : "cènt./kWh"} />
        </ChartCard>
      </div>

      <div className="mt-6">
        <ChartCard
          title="CO₂ i preu, respecte de la seva mitjana"
          subtitle="1 = mitjana de l'any. De dia van junts; de matinada, no."
          conclusion={
            <>
              Correlació horària de <b>{nf(s.corr_hourly, 2)}</b> (positiva tots els mesos). El conflicte és la matinada:
              barata però bruta (gas de nit). Qui només mirés el preu carregaria de nit; pel CO₂ cal carregar a migdia.
            </>
          }
          source={`De les 6 h més netes de cada dia, el ${nf(s.overlap_clean_cheap)} % són a la meitat barata; de les 6 més brutes, el ${nf(s.overlap_dirty_expensive)} % a la meitat cara.`}
        >
          <Legend items={[{ label: "CO₂", color: C.co2, shape: "line" }, { label: "Preu", color: C.money, shape: "line" }]} />
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={conflict} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis domain={[0.5, 1.8]} ticks={[0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8]} tickLine={false} axisLine={false} />
              <ReferenceLine y={1} stroke={C.axis} strokeDasharray="0" />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={hour(Number(label))}
                      rows={[
                        { label: "CO₂", value: `${nf(Number(payload[0].value), 2)}×`, color: C.co2 },
                        { label: "Preu", value: `${nf(Number(payload[1].value), 2)}×`, color: C.money },
                      ]}
                    />
                  ) : null
                }
              />
              <Line type="monotone" dataKey="co2_norm" stroke={C.co2} strokeWidth={2.5} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="price_norm" stroke={C.money} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="mt-6">
        <Decision>
          Carregar a <b>migdia</b> (xarxa neta i barata) i descarregar al <b>vespre</b> (bruta i cara), amb un segon
          cicle petit de matinada. I com que preu i CO₂ no sempre coincideixen, cal una regla que combini les dues —
          el tema de la pàgina següent.
        </Decision>
        <p className="mt-2 text-center text-[11px] text-ink-muted">Les hores punta (21 h) són alhora les més brutes i les més cares.</p>
      </div>
    </div>
  );
}

function BandChart({
  data,
  color,
  bandColor,
  unit,
  best,
  worst,
}: {
  data: { hour: number; mean: number; base: number; band: number }[];
  color: string;
  bandColor: string;
  unit: string;
  best: number;
  worst: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
        <YAxis tickLine={false} axisLine={false} />
        <ReferenceLine x={best} stroke={C.aqua} strokeWidth={1} label={{ value: `${best} h`, fontSize: 10, fill: C.muted, position: "insideBottomLeft" }} />
        <ReferenceLine x={worst} stroke={C.red} strokeWidth={1} label={{ value: `${worst} h`, fontSize: 10, fill: C.muted, position: "insideTopRight" }} />
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox title={hour(Number(label))} rows={[{ label: "Mitjana", value: `${nf(Number(payload.find((x) => x.dataKey === "mean")?.value ?? 0), 1)} ${unit}`, color }]} />
            ) : null
          }
        />
        <Area type="monotone" dataKey="base" stackId="b" stroke="none" fill="none" isAnimationActive={false} />
        <Area type="monotone" dataKey="band" stackId="b" stroke="none" fill={bandColor} fillOpacity={0.16} isAnimationActive={false} />
        <Line type="monotone" dataKey="mean" stroke={color} strokeWidth={2.5} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
