import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useScenarios, type ScenarioRow } from "../lib/data";
import { Card, ChartCard, Decision, ErrorBox, Kpi, Loading, SectionHeader } from "../components/ui";
import { Legend, TooltipBox } from "../components/charts";
import { C } from "../lib/theme";
import { eurCompact, nf } from "../lib/format";

const CAPS = [1, 2, 4, 8, 16];

export default function Sizing() {
  const { data, isLoading, error } = useScenarios();
  const [cap, setCap] = useState(4); // recomanació per defecte
  const [costKwh, setCostKwh] = useState(300);
  const [powerMode, setPowerMode] = useState<"prop" | "fixed">("prop");
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;

  const prop = data.proportional;
  const byCap = (rows: ScenarioRow[], c: number) => rows.find((r) => r.capacity_mwh === c);
  const sel = byCap(powerMode === "prop" ? prop : data.fixed_power, cap)!;
  const investment = cap * 1000 * costKwh;
  const payback = investment / sel.eur_year;

  const co2Chart = CAPS.map((c) => ({ cap: c, prop: byCap(prop, c)?.co2_t_year ?? 0, fixed: byCap(data.fixed_power, c)?.co2_t_year ?? 0 }));
  const eurChart = CAPS.map((c) => ({ cap: c, prop: byCap(prop, c)?.eur_year ?? 0, fixed: byCap(data.fixed_power, c)?.eur_year ?? 0 }));
  const marginal = prop.filter((r) => CAPS.includes(r.capacity_mwh) && r.marginal_co2_t != null).map((r) => ({ cap: r.capacity_mwh, m: r.marginal_co2_t as number }));
  const mAt = (c: number) => marginal.find((x) => x.cap === c)?.m ?? 0;
  const rec4 = byCap(prop, 4)!; // mida recomanada

  return (
    <div>
      <SectionHeader
        title="Quina mida de bateria hauria d'instal·lar la UPC?"
        lead="La pregunta de negoci. Cada mida mostra l'estalvi potencial anual estimat. Tria una capacitat per veure'n l'estalvi i el retorn; mou el cost per kWh per provar supòsits d'inversió."
      />

      {/* Selector + KPIs */}
      <Card className="mb-6 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-[13px] font-medium text-ink-secondary">Capacitat:</span>
          {CAPS.map((c) => {
            const rec = c === 4; // mida recomanada: sempre marcada en verd
            const active = cap === c;
            const cls = active
              ? rec ? "bg-good text-white" : "bg-upc text-white"
              : rec ? "bg-good/10 text-good ring-1 ring-good/40 hover:bg-good/20" : "bg-black/[0.05] text-ink-secondary hover:bg-black/[0.08]";
            return (
              <button key={c} onClick={() => setCap(c)} className={`rounded-lg px-3.5 py-1.5 text-[14px] font-semibold tabular transition-colors ${cls}`}>
                {c} MWh
              </button>
            );
          })}
          <span className="ml-1 rounded-full bg-good/10 px-2 py-0.5 text-[11px] font-medium text-good">4 MWh recomanada</span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="mr-1 text-[13px] font-medium text-ink-secondary">Potència:</span>
          <button onClick={() => setPowerMode("prop")} className={`rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors ${powerMode === "prop" ? "bg-upc text-white" : "bg-black/[0.05] text-ink-secondary hover:bg-black/[0.08]"}`}>
            Proporcional ({nf(byCap(prop, cap)!.power_kw)} kW)
          </button>
          <button onClick={() => setPowerMode("fixed")} className={`rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors ${powerMode === "fixed" ? "bg-upc text-white" : "bg-black/[0.05] text-ink-secondary hover:bg-black/[0.08]"}`}>
            Fixa 500 kW
          </button>
          <span className="text-[12px] text-ink-muted">· els KPIs i el retorn canvien en viu</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Kpi value={`${nf(sel.co2_t_year)} t`} label="CO₂ evitat l'any" tone="co2" />
          <Kpi value={eurCompact(sel.eur_year)} label="Estalvi a la factura l'any" tone="money" />
          <Kpi value={nf(sel.co2_pct, 1) + " %"} label="del CO₂ del campus" tone="co2" />
          <Kpi value={nf(sel.cycles_day, 2)} label="cicles al dia" sub={`potència ${nf(sel.power_kw)} kW`} />
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="CO₂ evitat l'any segons la mida"
          subtitle="Potència proporcional a la capacitat vs potència fixa de 500 kW."
          conclusionTone="co2"
          conclusion={
            <>
              Proporcional fins a <b>4 MWh</b> i després es frena. Sense ampliar la potència, s'estanca de seguida: la
              bateria no té prou kW per buidar-se a les hores dolentes.
            </>
          }
          source="Estalvi potencial anual, anualitzat des de 258 dies de dades."
        >
          <Legend items={[{ label: "Potència proporcional", color: C.co2, shape: "line" }, { label: "Potència fixa 500 kW", color: "#92d8b0", shape: "line" }]} />
          <SizingLine data={co2Chart} cap={cap} unit="t" fmt={(v) => nf(v)} main={C.co2} alt="#92d8b0" />
        </ChartCard>

        <ChartCard
          title="Estalvi a la factura l'any segons la mida"
          subtitle="Mateixa comparació, en euros."
          conclusion={
            <>
              Mateix patró: cada MWh ret igual fins a 4 MWh; més enllà, cada MWh afegit estalvia menys. La potència
              importa tant com la capacitat.
            </>
          }
        >
          <Legend items={[{ label: "Potència proporcional", color: C.money, shape: "line" }, { label: "Potència fixa 500 kW", color: "#74b8e2", shape: "line" }]} />
          <SizingLine data={eurChart} cap={cap} unit="€" fmt={(v) => eurCompact(v)} euro main={C.money} alt="#74b8e2" />
        </ChartCard>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <ChartCard
          title="Rendiment de cada MWh afegit (CO₂)"
          subtitle="Tones de CO₂ evitades l'any per cada MWh addicional (potència proporcional)."
          conclusionTone="co2"
          conclusion={
            <>
              Rendiments constants fins a <b>4 MWh</b> (~{nf(mAt(4), 1)} t/MWh) i decreixents després: de 4→8 MWh baixa a {nf(mAt(8), 1)}, i de
              8→16 MWh a {nf(mAt(16), 1)}. El punt d'inflexió és clar.
            </>
          }
        >
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={marginal} margin={{ top: 16, right: 8, bottom: 4, left: -16 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="cap" tickFormatter={(c) => `${c}`} tickLine={false} unit=" MWh" />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? <TooltipBox title={`fins a ${label} MWh`} rows={[{ label: "t CO₂ / MWh afegit", value: nf(Number(payload[0].value), 1), color: C.co2 }]} /> : null
                }
              />
              <Bar dataKey="m" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                {marginal.map((d, i) => (
                  <Cell key={i} fill={d.cap <= 4 ? C.co2 : C.axis} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Payback interactivo */}
        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Retorn de la inversió (orientatiu)</h3>
          <p className="mt-0.5 text-[13px] text-ink-secondary">
            Anys per recuperar la inversió només amb l'estalvi a la factura, per a la bateria de <b>{cap} MWh</b>.
          </p>
          <div className="mt-4 flex items-end gap-4">
            <div>
              <div className="text-[44px] font-bold leading-none tabular text-upc">{nf(payback, 1)}</div>
              <div className="text-[13px] text-ink-secondary">anys de retorn</div>
            </div>
            <div className="mb-1 text-[13px] leading-snug text-ink-secondary">
              Inversió ≈ <b>{eurCompact(investment)}</b>
              <br />
              Estalvi ≈ <b>{eurCompact(sel.eur_year)}</b>/any
            </div>
          </div>
          <div className="mt-5">
            <div className="mb-1 flex items-center justify-between text-[12px] text-ink-secondary">
              <span>Cost instal·lat suposat</span>
              <span className="tabular font-semibold text-ink">{nf(costKwh)} €/kWh</span>
            </div>
            <input
              type="range"
              min={150}
              max={500}
              step={25}
              value={costKwh}
              onChange={(e) => setCostKwh(Number(e.target.value))}
              className="w-full accent-upc"
            />
            <div className="flex justify-between text-[10px] text-ink-muted">
              <span>150</span>
              <span>500 €/kWh</span>
            </div>
          </div>
          <p className="mt-4 rounded-lg bg-warning/10 px-3 py-2 text-[12px] leading-snug text-[#7a5200]">
            El cost per kWh és un <b>supòsit nostre</b>, no una dada mesurada, i no inclou la degradació de la bateria
            (~500 cicles/any). Cal contrastar-ho amb UPC Sostenible.
          </p>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          La mida eficient és <b>~4 MWh amb {nf(rec4.power_kw)} kW</b>: fins aquí cada euro invertit ret igual que a la bateria
          estàndard de 2 MWh (evita ~{nf(rec4.co2_t_year)} t de CO₂ i ~{eurCompact(rec4.eur_year)} l'any); més enllà, cada MWh afegit ret cada cop menys. I cal{" "}
          <b>ampliar la potència alhora que la capacitat</b>, no només els kWh.
        </Decision>
      </div>
    </div>
  );
}

function SizingLine({
  data,
  cap,
  unit,
  fmt,
  euro,
  main,
  alt,
}: {
  data: { cap: number; prop: number; fixed: number }[];
  cap: number;
  unit: string;
  fmt: (v: number) => string;
  euro?: boolean;
  main: string;
  alt: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data} margin={{ top: 10, right: 16, bottom: 4, left: euro ? 6 : -12 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="cap" type="number" domain={[1, 16]} ticks={CAPS} tickFormatter={(c) => `${c}`} tickLine={false} unit=" MWh" />
        <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => (euro ? `${nf(v / 1000)}k` : nf(v))} width={euro ? 42 : 40} />
        <ReferenceLine x={cap} stroke={C.upc} strokeWidth={1} />
        <Tooltip
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipBox
                title={`${label} MWh`}
                rows={[
                  { label: "Proporcional", value: `${fmt(Number(payload[0].value))}${euro ? "" : " " + unit}`, color: main },
                  { label: "Fixa 500 kW", value: `${fmt(Number(payload[1].value))}${euro ? "" : " " + unit}`, color: alt },
                ]}
              />
            ) : null
          }
        />
        <Line type="monotone" dataKey="prop" stroke={main} strokeWidth={2.5} dot={{ r: 3, fill: main }} isAnimationActive={false} />
        <Line type="monotone" dataKey="fixed" stroke={alt} strokeWidth={2.5} dot={{ r: 3, fill: alt }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
