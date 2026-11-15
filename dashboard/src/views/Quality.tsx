import { CartesianGrid, ComposedChart, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useQuality } from "../lib/data";
import { Card, ChartCard, Decision, ErrorBox, Kpi, Loading, SectionHeader } from "../components/ui";
import { Legend, TooltipBox } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf } from "../lib/format";

export default function Quality() {
  const { data, isLoading, error } = useQuality();
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;
  const s = data.stats;

  // Perfil día medio
  const profile = data.night_profile.map((p) => ({ hour: p.hour, dataset: p.dataset_kw, real: p.real_kw }));

  // Ejemplo 2 días a 5 min
  const ex = data.example.map((e, i) => {
    const d = new Date(e.ts);
    return { idx: i, ts: e.ts, h: d.getHours(), min: d.getMinutes(), day: d.getDate(), dataset: e.dataset_kw, real: e.real_kw, frozen: e.frozen };
  });
  const exTicks = ex.filter((e) => e.min === 0 && e.h % 6 === 0).map((e) => e.idx);
  // Tramos congelados para sombrear
  const frozenBands: { x1: number; x2: number }[] = [];
  let start: number | null = null;
  ex.forEach((e, i) => {
    if (e.frozen && start == null) start = i;
    if (!e.frozen && start != null) {
      frozenBands.push({ x1: start, x2: i - 1 });
      start = null;
    }
  });
  if (start != null) frozenBands.push({ x1: start, x2: ex.length - 1 });

  return (
    <div>
      <SectionHeader
        title="Ens podem fiar de les dades?"
        lead="Un dashboard honest ha de dir on falla la mesura. El comptador del campus té dos problemes coneguts que afecten quins números es poden citar — i quins no — als informes de direcció."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={nf(s.frozen_pct, 1) + " %"} label="registres «congelats»" sub="de nit, 22:10–06:00: repeteixen l'últim valor" />
        <Kpi value={`${nf(s.night_cong_kw)}→${nf(s.night_real_kw)}`} label="consum nocturn (kW)" sub={`${nf(s.night_diff_pct, 0)} % sobre el real`} />
        <Kpi value={nf(s.com_fail_n)} label="fallades de comunicació" sub={`${nf(s.com_fail_pct, 2)} % dels registres marquen 0`} />
        <Kpi value={nf(s.zero_hours)} label="hores amb consum 0" sub="avaries puntuals del comptador" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="El comptador no es llegeix de nit"
          subtitle="13–15 de gener, dada cada 5 min. Zones grises = sense lectura (valor repetit)."
          conclusion={
            <>
              De 22:10 a 06:00 el dataset repeteix l'últim valor; el consum real (reconstruït amb l'energia acumulada
              que arriba a les 06:05) és clarament més baix.
            </>
          }
          source="El comptador entrega a les 06:05 l'energia consumida durant la nit."
        >
          <Legend items={[{ label: "Dataset (potència)", color: C.blue, shape: "line" }, { label: "Consum real", color: C.orange, shape: "line" }]} />
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={ex} margin={{ top: 8, right: 12, bottom: 4, left: 2 }}>
              <CartesianGrid vertical={false} />
              {frozenBands.map((b, i) => (
                <ReferenceArea key={i} x1={b.x1} x2={b.x2} fill="#000" fillOpacity={0.045} stroke="none" />
              ))}
              <XAxis dataKey="idx" type="number" domain={["dataMin", "dataMax"]} ticks={exTicks} tickFormatter={(i) => (ex[i] ? `${ex[i].day}/1 ${hour(ex[i].h)}` : "")} tickLine={false} tick={{ fontSize: 10 }} />
              <YAxis domain={[600, 1800]} tickLine={false} axisLine={false} width={44} unit=" kW" />
              <Tooltip content={<ExTooltip ex={ex} />} />
              <Line type="monotone" dataKey="dataset" stroke={C.blue} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="real" stroke={C.orange} strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="El dia mitjà: dataset vs consum real"
          subtitle="Consum mitjà en dies laborables, per hora."
          conclusion={
            <>
              El consum nocturn real és de <b>{nf(s.night_real_kw)} kW</b>, no <b>{nf(s.night_cong_kw)} kW</b>: un{" "}
              {nf(Math.abs(s.night_diff_pct), 0)} % menys. El dataset sobreestima ~{nf(s.over_kwh_night)} kWh cada nit
              ({nf(s.over_pct_daily, 1)} % del consum diari).
            </>
          }
        >
          <Legend items={[{ label: "Dataset oficial", color: C.blue, shape: "line" }, { label: "Consum real reconstruït", color: C.orange, shape: "line" }]} />
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={profile} margin={{ top: 8, right: 12, bottom: 4, left: 2 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis domain={[600, 1200]} tickLine={false} axisLine={false} width={44} unit=" kW" />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={hour(Number(label))}
                      rows={[
                        { label: "Dataset", value: `${nf(Number(payload[0].value))} kW`, color: C.blue },
                        { label: "Real", value: `${nf(Number(payload[1].value))} kW`, color: C.orange },
                      ]}
                    />
                  ) : null
                }
              />
              <Line type="monotone" dataKey="dataset" stroke={C.blue} strokeWidth={2.5} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="real" stroke={C.orange} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Variantes de datos */}
      <Card className="mt-6 p-5">
        <h3 className="text-[15px] font-semibold text-ink">Canvia això les decisions?</h3>
        <p className="mt-0.5 text-[13px] text-ink-secondary">
          Estalvi en percentatge segons com es tractin les dades. Corregir-les <b>no canvia què fa la bateria</b>
          (el campus sempre consum &gt; 500 kW); només canvia el percentatge, perquè canvia la referència.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-hair text-left text-ink-secondary">
                <th className="py-2 pr-4 font-medium">Tractament de les dades</th>
                <th className="py-2 pr-4 text-right font-medium">CO₂ estalviat</th>
                <th className="py-2 text-right font-medium">Cost estalviat</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {data.variants.map((v) => (
                <tr key={v.variant} className={`border-b border-hair last:border-0 ${v.variant === "oficial" ? "bg-upc/[0.04]" : ""}`}>
                  <td className="py-2 pr-4 text-ink">
                    {v.label}
                    {v.variant === "oficial" && <span className="ml-2 rounded-full bg-upc/10 px-2 py-0.5 text-[10px] font-medium text-upc">la que fem servir</span>}
                  </td>
                  <td className="py-2 pr-4 text-right font-semibold text-co2">{nf(v.d_co2_pct, 2)} %</td>
                  <td className="py-2 text-right font-semibold text-money">{nf(v.d_cost_pct, 2)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[12px] leading-snug text-ink-muted">
          Les decisions de la bateria són les mateixes amb qualsevol tractament; el que es mou és només la xifra que es
          pot citar, perquè la lectura nocturna del comptador està congelada i infla la referència de consum.
        </p>
      </Card>

      <div className="mt-6">
        <Decision>
          Les <b>decisions</b> (carregar/descarregar, mida, objectiu) són robustes: no depenen de l'error nocturn. Però
          cal <b>citar bé els números</b>: l'estalvi en t i € no canvia, el <b>percentatge</b> sí (del 6,0 % oficial al
          6,5 % amb consum real). En parlar amb UPC Sostenible, dir «segons el dataset» o usar les xifres reals
          (~750 t, 24,7 MWh/dia).
        </Decision>
      </div>
    </div>
  );
}

function ExTooltip({ ex, active, payload }: any) {
  if (!active || !payload?.length) return null;
  const idx = payload[0].payload.idx as number;
  const p = ex[idx];
  if (!p) return null;
  return (
    <TooltipBox
      title={`${p.day}/1 ${hour(p.h)}${p.min ? ":" + String(p.min).padStart(2, "0") : ""}`}
      rows={[
        { label: "Dataset", value: `${nf(p.dataset)} kW`, color: C.blue },
        ...(p.real != null ? [{ label: "Real", value: `${nf(p.real)} kW`, color: C.orange }] : []),
        ...(p.frozen ? [{ label: "estat", value: "sense lectura" }] : []),
      ]}
    />
  );
}
