import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHmForecast, useHmKpis, useHmStrategies, useKpis, useStrategies } from "../lib/data";
import { Card, ChartCard, ErrorBox, Loading, SectionHeader } from "../components/ui";
import { TooltipBox } from "../components/charts";
import { nf } from "../lib/format";
import { C } from "../lib/theme";

/** Dades del repte (Datathon): context tècnic i totes les comparatives amb altres models i versions.
 *  No forma part del que veuria l'equip de la UPC: és material per al jurat. */
export default function GeneralInfo() {
  const { data: k, isLoading, error } = useKpis();
  const { data: hm } = useHmKpis();
  const { data: strat } = useStrategies();
  const { data: hmStrat } = useHmStrategies();
  const { data: hmFc } = useHmForecast();
  if (isLoading || !k) return error ? <ErrorBox error={error} /> : <Loading />;

  return (
    <div>
      <SectionHeader
        title="Challenge data"
        lead="Context tècnic i totes les comparatives amb altres models (línies de base, l'òptim teòric i les nostres versions anteriors). Aquest material no forma part del que veuria l'equip de la UPC: és el suport per al jurat del Datathon FME 2026 (repte UPC Sostenible)."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h3 className="text-[16px] font-semibold text-ink">Les dues instal·lacions</h3>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-hair text-left text-ink-secondary">
                  <th className="py-2 pr-3 font-medium"></th>
                  <th className="py-2 pr-3 font-medium">Actual</th>
                  <th className="py-2 font-medium">Ampliada</th>
                </tr>
              </thead>
              <tbody>
                <Row k="Bateria" a="2 MWh · ±500 kW" b="6 MWh · ±1.500 kW" />
                <Row k="Solar" a="petita" b="12× més gran" />
                <Row k="Previsió de mercat" a="24 h exactes" b="només 3 h" />
                <Row k="Dades extra" a="consum i solar" b="+ meteo" />
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[12px] leading-snug text-ink-muted">
            Al repte s'anomenen «mode estàndard» i «hard mode». Al dashboard es presenten com la instal·lació actual i
            l'ampliació proposada.
          </p>
        </Card>

        <Card className="p-6">
          <h3 className="text-[16px] font-semibold text-ink">Com es mesura el rendiment</h3>
          <div className="mt-3 rounded-xl bg-plane px-4 py-3 text-center text-[15px] text-ink">
            Score = <span className="font-semibold text-co2">0,70 · ΔCO₂%</span> +{" "}
            <span className="font-semibold text-money">0,30 · ΔCost%</span> − penalització
          </div>
          <p className="mt-3 text-[13px] leading-snug text-ink-secondary">
            Es compara el campus amb bateria contra el campus sense bateria: percentatge de CO₂ i de cost evitats,
            amb un pes de 70/30. Cada acció impossible (infracció) resta; el nostre objectiu són sempre <b>0</b>.
          </p>
        </Card>
      </div>

      {/* Comparatives amb altres models */}
      <div className="mt-8 mb-4 max-w-3xl">
        <h2 className="text-[20px] font-bold tracking-tight text-ink">Comparatives amb altres models</h2>
        <p className="mt-1 text-[14px] leading-relaxed text-ink-secondary">
          Com se situa el nostre agent respecte de les línies de base, l'òptim amb informació perfecta i les nostres
          pròpies versions anteriors.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {strat && (
          <ChartCard
            title="Instal·lació actual · score per estratègia"
            subtitle="Sobre la validació oficial. En gris les referències; en blau el nostre agent (MPC)."
            source="La plantilla oficial, a més, comet 7 infraccions."
          >
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={strat.comparison} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 96 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 6.6]} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tickLine={false} axisLine={false} width={94} tick={{ fontSize: 11 }} />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <TooltipBox
                        title={String(label)}
                        rows={[
                          { label: "Score", value: nf(Number(payload[0].value), 2), color: C.blue },
                          { label: "ΔCO₂", value: `${nf((payload[0].payload as any).d_co2_pct, 1)} %` },
                          { label: "ΔCost", value: `${nf((payload[0].payload as any).d_cost_pct, 1)} %` },
                        ]}
                      />
                    ) : null
                  }
                />
                <Bar dataKey="score" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  <LabelList dataKey="score" position="right" formatter={(v: number) => nf(v, 2)} style={{ fontSize: 12, fill: C.ink }} />
                  {strat.comparison.map((c, i) => (
                    <Cell key={i} fill={c.key === "mpc" ? C.blue : c.key === "oracle" ? C.upc : C.axis} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {hmStrat && (
          <ChartCard
            title="Instal·lació ampliada · score per estratègia"
            subtitle="Validació reservada. En taronja el nostre agent; l'òptim coneix tot el futur."
          >
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={hmStrat.ladder} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 140 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 24]} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={138} tickLine={false} axisLine={false} interval={0} />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <TooltipBox title={String(label)} rows={[
                        { label: "Score", value: nf(Number(payload[0].value), 2), color: C.orange },
                        { label: "ΔCO₂", value: `${nf((payload[0].payload as any).co2_pct, 1)} %` },
                        { label: "ΔCost", value: `${nf((payload[0].payload as any).cost_pct, 1)} %` },
                      ]} />
                    ) : null
                  }
                />
                <Bar dataKey="score" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  <LabelList dataKey="score" position="right" formatter={(v: number) => nf(v, 2)} style={{ fontSize: 12, fill: C.ink }} />
                  {hmStrat.ladder.map((l, i) => (
                    <Cell key={i} fill={l.key === "v7" ? C.orange : l.key === "oracle" ? C.upc : C.axis} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {hmFc && (
          <ChartCard
            title="Instal·lació ampliada · quant val preveure?"
            subtitle="Score segons la informació disponible. En taronja, el nostre agent."
            source="Òptim amb tot el futur conegut: el sostre."
          >
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={hmFc.value_ladder} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 150 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" domain={[0, 24]} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 10 }} width={148} tickLine={false} axisLine={false} interval={0} />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.04)" }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? <TooltipBox title={String(label)} rows={[{ label: "Score", value: nf(Number(payload[0].value), 2), color: C.orange }]} /> : null
                  }
                />
                <Bar dataKey="score" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  <LabelList dataKey="score" position="right" formatter={(v: number) => nf(v, 2)} style={{ fontSize: 12, fill: C.ink }} />
                  {hmFc.value_ladder.map((d, i) => (
                    <Cell key={i} fill={d.is_us ? C.orange : C.axis} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {hmStrat && (
          <Card className="p-5">
            <h3 className="text-[15px] font-semibold text-ink">Instal·lació ampliada · com hem anat millorant</h3>
            <p className="mt-0.5 text-[13px] text-ink-secondary">Score a la validació reservada per versió de l'agent.</p>
            <div className="mt-4 space-y-2.5">
              {hmStrat.versions.map((v, i) => {
                const w = (v.score / 22.4) * 100;
                const last = i === hmStrat.versions.length - 1;
                return (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-36 shrink-0 text-right text-[12px] text-ink-secondary">{v.name}</div>
                    <div className="relative h-6 flex-1 rounded bg-black/[0.04]">
                      <div className="flex h-full items-center rounded px-2" style={{ width: `${w}%`, background: last ? C.orange : C.axis }}>
                        <span className={`tabular text-[12px] font-semibold ${last ? "text-white" : "text-ink"}`}>{nf(v.score, 2)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 space-y-2 rounded-lg bg-plane px-3 py-2.5 text-[12px] leading-snug text-ink-secondary">
              <p>
                Casa i web no són comparables: el conjunt públic és un altre grup de setmanes, més favorable (la v7 fa 20,79 a casa
                i <b>24,10</b> a la web).
              </p>
              <p>
                Al <b>rànquing públic</b> (SanHackobos): v6 <b>23,70</b> · v8 <b>24,06</b> · v7 <b>24,10</b> —{" "}
                <b>2a de 37 equips</b>, a 0,15 del rècord (24,25). Ens quedem amb la v7.
              </p>
            </div>
          </Card>
        )}
      </div>

      <div className="mt-8 mb-4 max-w-3xl">
        <h2 className="text-[20px] font-bold tracking-tight text-ink">Rendiment, rànquing i honestedat</h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h3 className="text-[16px] font-semibold text-ink">Rendiment del controlador (validació)</h3>
          <p className="mt-0.5 text-[13px] text-ink-secondary">
            El controlador arriba a prop de l'òptim físic (el màxim amb informació perfecta del futur).
          </p>
          <div className="mt-4 space-y-3">
            <PerfBar label="Instal·lació actual" value={k.agent_score} max={k.oracle_score} note={`${nf(k.pct_of_max, 1)} % del màxim`} />
            {hm && <PerfBar label="Instal·lació ampliada" value={hm.agent_score} max={hm.oracle_score} note={`${nf(hm.pct_of_max, 1)} % del màxim`} />}
          </div>
          <p className="mt-3 text-[12px] leading-snug text-ink-muted">
            La distància que queda és física (la mida de la bateria i les pèrdues), no de l'algorisme: amb el futur
            perfectament conegut tampoc es podria superar.
          </p>
        </Card>

        <Card className="p-6">
          <h3 className="text-[16px] font-semibold text-ink">Rànquing públic del repte</h3>
          <ul className="mt-3 space-y-2.5 text-[13px] leading-snug text-ink-secondary">
            <li>
              · <b className="text-ink">Instal·lació actual:</b> els bons equips estan empatats al màxim (rècord 6,44);
              el nostre agent (equip <b>SanHackobos</b>) hi és amb <b>6,43</b>, 0 infraccions.
            </li>
            {hm && (
              <li>
                · <b className="text-ink">Instal·lació ampliada:</b> <b>{nf(hm.public_v7, 2)} punts</b> — <b>{hm.public_rank}</b>,
                a 0,15 del rècord ({nf(hm.public_record, 2)}).
              </li>
            )}
            <li>· La nota de casa (validació reservada) i la de la web no són comparables: el conjunt públic és un altre grup de setmanes, més favorable.</li>
          </ul>
        </Card>
      </div>

      {strat && (
        <Card className="mt-6 p-6">
          <h3 className="text-[16px] font-semibold text-ink">Per què el màxim és ~6 % (instal·lació actual)</h3>
          <p className="mt-0.5 text-[13px] text-ink-secondary">El sostre el posa la mida de la bateria, no l'algorisme: traient una restricció física cada cop.</p>
          <div className="mt-4 space-y-2">
            {[...strat.ceiling].map((c) => {
              const w = (c.score / 13) * 100;
              return (
                <div key={c.label} className="flex items-center gap-3">
                  <div className="w-56 shrink-0 text-right text-[12px] text-ink-secondary">{c.label}</div>
                  <div className="relative h-5 flex-1 rounded bg-black/[0.04]">
                    <div className="flex h-full items-center rounded px-2" style={{ width: `${w}%`, background: c.is_real ? C.upc : C.axis }}>
                      <span className={`tabular text-[11px] font-semibold ${c.is_real ? "text-white" : "text-ink"}`}>{nf(c.score, 1)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      <Card className="mt-6 p-6">
        <h3 className="text-[16px] font-semibold text-ink">Honestedat de les dades</h3>
        <ul className="mt-3 space-y-2 text-[13px] leading-snug text-ink-secondary">
          <li>· El mapa del campus reparteix el consum <b>total</b> mesurat per tipus d'edifici: és un model il·lustratiu, no una mesura per edifici.</li>
          <li>· El comptador no es llegeix de nit (22–06 h); el consum nocturn s'estima amb l'energia acumulada.</li>
          <li>· Les xifres anuals (tones, euros) s'anualitzen des de les dades disponibles i suposen que la bateria no es degrada.</li>
          <li>· Dades oficials del repte, del {k.validation_start} al {k.validation_end} per a la validació.</li>
        </ul>
      </Card>
    </div>
  );
}

function Row({ k, a, b }: { k: string; a: string; b: string }) {
  return (
    <tr className="border-b border-hair last:border-0">
      <td className="py-2 pr-3 font-medium text-ink">{k}</td>
      <td className="py-2 pr-3 text-ink-secondary">{a}</td>
      <td className="py-2 font-medium text-ink">{b}</td>
    </tr>
  );
}

function PerfBar({ label, value, max, note }: { label: string; value: number; max: number; note: string }) {
  const w = (value / max) * 100;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[12px]">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-ink-muted">{note}</span>
      </div>
      <div className="relative h-6 w-full overflow-hidden rounded-lg bg-black/[0.05]">
        <div className="stripes h-full rounded-lg" style={{ width: `${w}%`, background: C.upc }} />
        <div className="absolute inset-y-0 right-2 flex items-center text-[11px] font-medium text-ink-secondary">
          {nf(value, 2)} / {nf(max, 2)}
        </div>
      </div>
    </div>
  );
}
