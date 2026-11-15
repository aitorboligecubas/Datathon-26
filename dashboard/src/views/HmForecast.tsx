import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHmForecast } from "../lib/data";
import { Card, ChartCard, Decision, ErrorBox, Kpi, Loading, SectionHeader } from "../components/ui";
import { TooltipBox } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf } from "../lib/format";


export default function HmForecast() {
  const { data, isLoading, error } = useHmForecast();
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;

  return (
    <div>
      <SectionHeader
        title="Preveure el futur"
        lead="Aquí només es coneixen el preu i el CO₂ de les 3 hores vinents (la resta, 0). Sense previsió, el pla és cec. L'agent preveu preu, CO₂, solar i consum, i actua amb un marge perquè la previsió s'equivoca."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={`${data.known_hours} h`} label="de mercat conegut" sub="la resta s'ha de preveure" tone="accent" />
        <Kpi value="1,4×" label="marge de seguretat" sub="sobre l'error típic de la previsió" tone="good" />
        <Kpi value={`${nf(data.market_err_pct, 1)} %`} label="error de la previsió de mercat" sub="del pes mitjà de l'hora" />
        <Kpi value={`±${nf(data.solar_step_kw)} kW`} label="canvi típic de la solar" sub="d'una hora a la següent" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.25fr_1fr]">
        <ChartCard
          title="Incertesa de la previsió per hora del dia"
          subtitle="Error típic (desviació) de la previsió del consum net, per hora."
          conclusion={
            <>
              L'error és màxim a migdia (la solar canvia molt i de pressa). Per això l'agent aplica un <b>marge de
              seguretat</b>: descarrega una mica menys i carrega una mica més del previst (1,4× l'error típic).
            </>
          }
        >
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={data.net_sd} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis tickLine={false} axisLine={false} unit=" kW" width={48} />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? <TooltipBox title={hour(Number(label))} rows={[{ label: "Error típic", value: `±${nf(Number(payload[0].value))} kW`, color: C.load }]} /> : null
                }
              />
              <Bar dataKey="kw" fill={C.load} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Com preveu l'agent</h3>
          <ol className="mt-3 space-y-2.5 text-[13px] leading-snug text-ink-secondary">
            <li>
              <b className="text-ink">1. Preu i CO₂.</b> Un perfil per mes, tipus de dia i hora, més una regressió amb 13 pistes
              (les 3 h conegudes, les últimes 6 i 24 h, ahir i abans-d'ahir…). Cada setmana arrenca amb la memòria dels 7 dies previs.
            </li>
            <li>
              <b className="text-ink">2. Solar i consum.</b> «Cel clar» de la data corregit per la claredat d'avui; el consum, el
              perfil de la setmana corregit per la desviació de l'hora anterior. Els festius compten com a diumenge.
            </li>
            <li>
              <b className="text-ink">3. Marge de seguretat.</b> Com que descarregar de més és tirar energia i carregar de menys és
              perdre excedent, es deixa un marge d'1,4× l'error típic mesurat.
            </li>
          </ol>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          La <b>previsió</b> és el que fa que la bateria gran aprofiti l'excedent sense tirar energia descarregant a cegues.
          L'error residual de la solar (±{nf(data.solar_step_kw)} kW d'una hora a la següent) és irreduïble amb les dades que
          dona l'entorn, i es gestiona amb el marge de seguretat, no eliminant-lo.
        </Decision>
      </div>
    </div>
  );
}
