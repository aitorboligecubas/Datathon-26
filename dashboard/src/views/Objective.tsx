import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useObjective } from "../lib/data";
import { ChartCard, Card, Decision, ErrorBox, Loading, SectionHeader } from "../components/ui";
import { Legend, TooltipBox } from "../components/charts";
import { C } from "../lib/theme";
import { nf } from "../lib/format";

export default function Objective() {
  const { data, isLoading, error } = useObjective();
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;
  const rows = data.rows;
  const reto = rows.find((r) => r.is_reto)!;
  const soloCost = rows.find((r) => r.label.includes("0/100"))!;
  const soloCo2 = rows.find((r) => r.label.includes("100/0"))!;

  const chartData = rows.map((r) => ({ name: r.label.split(" (")[0], short: r.label.match(/\(([^)]+)\)/)?.[1] ?? "", co2: r.d_co2_pct, cost: r.d_cost_pct, score: r.score, is_reto: r.is_reto }));

  return (
    <div>
      <SectionHeader
        title="Què ha d'optimitzar l'agent: CO₂, cost o totes dues?"
        lead="El planificador minimitza el «pes» de l'energia comprada. Canviant el pes entre emissions i euros, s'obtenen estratègies diferents. Aquí es veu què es guanya i què es perd amb cada tria."
      />

      <ChartCard
        title="Estalvi de CO₂ i de cost segons l'objectiu"
        subtitle="Les dues sèries són percentatges d'estalvi → mateix eix. 70/30 = prioritat a les emissions."
        conclusionTone="co2"
        conclusion={
          <>
            Gestionar <b>només pel preu</b> (0/100) aconsegueix el màxim estalvi econòmic ({nf(soloCost.d_cost_pct, 1)} %) però
            perd gairebé la meitat del CO₂ ({nf(soloCost.d_co2_pct, 1)} % vs {nf(soloCo2.d_co2_pct, 1)} %). El{" "}
            <b>70/30</b> queda a prop del màxim de CO₂ i hi suma l'estalvi econòmic.
          </>
        }
        source="Estalvi potencial estimat per a cada ponderació."
      >
        <Legend items={[{ label: "ΔCO₂ %", color: C.co2 }, { label: "ΔCost %", color: C.money }]} />
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 16, right: 12, bottom: 4, left: -14 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} />
            <XAxis dataKey="name" tickLine={false} tick={{ fontSize: 12 }} interval={0} />
            <YAxis tickLine={false} axisLine={false} unit=" %" />
            <Tooltip
              cursor={{ fill: "rgba(0,0,0,0.04)" }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipBox
                    title={String(label)}
                    rows={[
                      { label: "ΔCO₂", value: `${nf(Number(payload[0].value), 2)} %`, color: C.co2 },
                      { label: "ΔCost", value: `${nf(Number(payload[1].value), 2)} %`, color: C.money },
                    ]}
                  />
                ) : null
              }
            />
            <Bar dataKey="co2" fill={C.co2} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="cost" fill={C.money} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <ChartCard
          title="Índex combinat de cada objectiu"
          subtitle="Combina el 70 % d'estalvi de CO₂ amb el 30 % d'estalvi de cost."
          conclusion={
            <>
              Ponderar <b>70 % CO₂ + 30 % cost</b> és el que dona el millor equilibri global ({nf(reto.score, 2)}):
              prioritza les emissions sense perdre estalvi econòmic.
            </>
          }
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 90 }}>
              <CartesianGrid horizontal={false} />
              <XAxis type="number" domain={[0, 7]} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="short" tickLine={false} axisLine={false} width={86} tick={{ fontSize: 11 }} />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox title={String(label)} rows={[{ label: "Índex", value: nf(Number(payload[0].value), 2), color: C.upc }]} />
                  ) : null
                }
              />
              <Bar dataKey="score" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                <LabelList dataKey="score" position="right" formatter={(v: number) => nf(v, 2)} style={{ fontSize: 12, fill: C.ink }} />
                {chartData.map((d, i) => (
                  <Cell key={i} fill={d.is_reto ? C.upc : C.axis} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">El missatge per a UPC Sostenible</h3>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-secondary">
            Una bateria gestionada «per preu» — el més habitual al mercat — <b>no</b> és el mateix que una gestionada
            per emissions. Amb aquestes dades, optimitzar només el cost deixa pel camí la meitat de l'estalvi de CO₂.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <MiniStat title="Només preu" co2={soloCost.d_co2_pct} cost={soloCost.d_cost_pct} />
            <MiniStat title="Repte 70/30" co2={reto.d_co2_pct} cost={reto.d_cost_pct} highlight />
          </div>
          <p className="mt-4 text-[13px] leading-snug text-ink-secondary">
            Passar de «només preu» a 70/30 gairebé <b>duplica</b> l'estalvi d'emissions
            (+{nf(reto.d_co2_pct - soloCost.d_co2_pct, 1)} punts de CO₂) a canvi de només
            −{nf(soloCost.d_cost_pct - reto.d_cost_pct, 1)} punts de cost.
          </p>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          Mantenir l'objectiu <b>70/30</b> (prioritat a les emissions): descarbonitza sense renunciar a gairebé res d'estalvi
          econòmic. Per a un desplegament real, és l'argument per gestionar la bateria <b>per emissions</b>, no per preu.
        </Decision>
      </div>
    </div>
  );
}

function MiniStat({ title, co2, cost, highlight }: { title: string; co2: number; cost: number; highlight?: boolean }) {
  return (
    <div className={`rounded-lg px-3 py-2.5 ${highlight ? "bg-upc/[0.07]" : "bg-plane"}`}>
      <div className={`text-[12px] font-semibold ${highlight ? "text-upc" : "text-ink-secondary"}`}>{title}</div>
      <div className="mt-1.5 flex items-baseline gap-1 tabular">
        <span className="text-[18px] font-semibold text-co2">{nf(co2, 1)}%</span>
        <span className="text-[11px] text-ink-muted">CO₂</span>
      </div>
      <div className="flex items-baseline gap-1 tabular">
        <span className="text-[18px] font-semibold text-money">{nf(cost, 1)}%</span>
        <span className="text-[11px] text-ink-muted">cost</span>
      </div>
    </div>
  );
}
