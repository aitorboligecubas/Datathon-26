import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useQuality } from "../lib/data";
import { Card, ChartCard, Decision, ErrorBox, Loading, SectionHeader } from "../components/ui";
import { Legend, TooltipBox } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf } from "../lib/format";

const WEATHER = [
  { name: "Irradiància (W/m²)", why: "La pista més directa de la solar: quanta llum arriba al panell ara mateix." },
  { name: "Temperatura del panell (°C)", why: "Un panell calent produeix una mica menys; ajuda a afinar la previsió solar." },
  { name: "Temperatura ambient (°C)", why: "Relacionada amb el consum de climatització del campus." },
  { name: "Velocitat del vent (m/s)", why: "Refreda els panells i, a escala d'Espanya, mou el mix elèctric (preu i CO₂)." },
];

export default function HmData() {
  const { data, isLoading, error } = useQuality();
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;
  const s = data.stats;
  const profile = data.night_profile.map((p) => ({ hour: p.hour, dataset: p.dataset_kw, real: p.real_kw }));

  return (
    <div>
      <SectionHeader
        title="Dades noves i honestedat"
        lead="La bateria ampliada rep també la meteo de l'hora anterior (irradiància, temperatures i vent) com a pista per preveure. I com sempre, el comptador té límits coneguts que cal tractar amb cura."
      />

      <Card className="p-5">
        <h3 className="text-[15px] font-semibold text-ink">La nova entrada: la meteo de l'hora anterior</h3>
        <p className="mt-0.5 text-[13px] text-ink-secondary">
          A cada hora, l'entorn ampliat dona quatre mesures meteorològiques de l'hora anterior (a més del consum i la solar).
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WEATHER.map((w) => (
            <div key={w.name} className="rounded-lg bg-plane px-3 py-2.5">
              <div className="text-[13px] font-semibold text-ink">{w.name}</div>
              <div className="mt-1 text-[12px] leading-snug text-ink-secondary">{w.why}</div>
            </div>
          ))}
        </div>
        <p className="mt-4 rounded-lg bg-warning/10 px-3 py-2 text-[12px] leading-snug text-[#7a5200]">
          <b>Lectura honesta.</b> La meteo arriba de l'hora <b>anterior</b>, no de la que es vol preveure. Ajuda al marge, però no
          elimina l'error de la solar (±142 kW d'una hora a la següent): el límit és físic, no de dades.
        </p>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="El comptador no es llegeix de nit"
          subtitle="Consum mitjà en dies laborables, per hora: dataset vs consum real reconstruït."
          conclusion={
            <>
              De 22 a 06 h el comptador repeteix l'últim valor; el consum real és un <b>{nf(Math.abs(s.night_diff_pct), 0)} %</b> més
              baix ({nf(s.night_real_kw)} kW en lloc de {nf(s.night_cong_kw)}). Aquí això és conegut i exacte, i el previsor
              el fa servir.
            </>
          }
          source={`Comptador congelat el ${nf(s.frozen_pct, 1)} % dels registres (22:10–06:00).`}
        >
          <Legend items={[{ label: "Dataset", color: C.blue, shape: "line" }, { label: "Consum real", color: C.orange, shape: "line" }]} />
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={profile} margin={{ top: 8, right: 12, bottom: 4, left: 2 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis domain={[600, 1200]} tickLine={false} axisLine={false} width={44} unit=" kW" />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox title={hour(Number(label))} rows={[
                      { label: "Dataset", value: `${nf(Number(payload[0].value))} kW`, color: C.blue },
                      { label: "Real", value: `${nf(Number(payload[1].value))} kW`, color: C.orange },
                    ]} />
                  ) : null
                }
              />
              <Line type="monotone" dataKey="dataset" stroke={C.blue} strokeWidth={2.5} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="real" stroke={C.orange} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Com es tracten les dades</h3>
          <ul className="mt-3 space-y-2.5 text-[13px] leading-snug text-ink-secondary">
            <li>
              <b className="text-ink">Festius com a diumenge.</b> Els festius nacionals i els del campus (la Mercè, Nadal, Sant Joan)
              es tracten com a diumenge, perquè el consum i el preu s'hi assemblen.
            </li>
            <li>
              <b className="text-ink">Final per calendari.</b> Amb només 3 h de previsió, el final del període (31/08/2026) no es veu a les
              dades: es dedueix del calendari per arribar amb la bateria buida.
            </li>
            <li>
              <b className="text-ink">Robustesa.</b> El sistema es prova contra observacions deformades, avaries del
              comptador i canvi d'hora: s'exigeix 0 infraccions i 0 excepcions.
            </li>
          </ul>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          Les decisions de la instal·lació ampliada són robustes i honestes: la meteo ajuda a la previsió però no elimina la
          incertesa de la solar, i per això la bateria actua sempre amb un marge de seguretat.
        </Decision>
      </div>
    </div>
  );
}
