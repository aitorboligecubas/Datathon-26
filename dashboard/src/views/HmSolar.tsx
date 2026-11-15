import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useHmSolar } from "../lib/data";
import { Card, ChartCard, Decision, ErrorBox, Kpi, Loading, SectionHeader } from "../components/ui";
import { Legend, TooltipBox, AreaGradient } from "../components/charts";
import { C } from "../lib/theme";
import { hour, nf } from "../lib/format";

export default function HmSolar() {
  const { data, isLoading, error } = useHmSolar();
  if (isLoading || !data) return error ? <ErrorBox error={error} /> : <Loading />;
  const s = data.stats;
  const hourly = data.hourly.map((h) => ({ ...h, surplusArea: Math.max(h.pv_kw - h.load_kw, 0) }));

  return (
    <div>
      <SectionHeader
        title="La solar ara compta: 12 vegades més gran"
        lead="Amb la bateria ampliada la fotovoltaica és 12× més gran. A migdia la producció s'acosta al consum i alguns dies el supera: aquest excedent es regala a la xarxa a 0 €. La feina nova de la bateria és guardar-lo."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={`${nf(s.pv_peak_kw)} kW`} label="pic solar" sub={`a les ${s.pv_peak_hour} h (×${nf(s.pv_factor, 0)} vs estàndard)`} tone="solar" />
        <Kpi value={`${nf(s.surplus_hours_pct, 1)} %`} label="d'hores amb excedent" sub="producció > consum" tone="solar" />
        <Kpi value={`${nf(s.export_base_kwh_day)} kWh`} label="excedent diari sense bateria" sub="es regalaria a la xarxa" />
        <Kpi value={`${nf(s.export_rescued_pct, 0)} %`} label="aprofitat amb la bateria" sub={`només ${nf(s.export_v8_solar_day)} kWh/dia es perden`} tone="good" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <ChartCard
          title="Producció solar i consum per hora del dia"
          subtitle="Mitjana de l'any. La zona taronja és l'excedent (solar per sobre del consum)."
          conclusion={
            <>
              A migdia la solar (pic <b>{nf(s.pv_peak_kw)} kW</b> a les {s.pv_peak_hour} h) s'acosta al consum i alguns dies el
              supera. Aquest excedent és el que la bateria ha de guardar per al pic del vespre.
            </>
          }
          source={`Solar ja multiplicada per ${nf(s.pv_factor, 0)}. Consum del campus entre ${nf(s.load_min_kw)} i ${nf(s.load_max_kw)} kW.`}
        >
          <Legend items={[{ label: "Solar", color: C.solar, shape: "line" }, { label: "Consum", color: C.load, shape: "line" }, { label: "Excedent", color: C.solar }]} />
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={hourly} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => (h % 3 === 0 ? String(h) : "")} tickLine={false} />
              <YAxis tickLine={false} axisLine={false} unit=" kW" width={54} />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <TooltipBox
                      title={hour(Number(label))}
                      rows={[
                        { label: "Solar", value: `${nf((payload[0].payload as any).pv_kw)} kW`, color: C.solar },
                        { label: "Consum", value: `${nf((payload[0].payload as any).load_kw)} kW`, color: C.load },
                        { label: "Excedent", value: `${nf((payload[0].payload as any).surplusArea)} kW`, color: C.solar },
                      ]}
                    />
                  ) : null
                }
              />
              <Area type="monotone" dataKey="load_kw" stroke="none" fill="none" isAnimationActive={false} />
              <AreaGradient id="solSurplus" color={C.solar} top={0.45} bottom={0.05} />
              <Area type="monotone" dataKey="surplusArea" stroke="none" fill="url(#solSurplus)" isAnimationActive={false} baseValue={0} />
              <Line type="monotone" dataKey="pv_kw" stroke={C.solar} strokeWidth={2.5} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="load_kw" stroke={C.load} strokeWidth={2.5} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Producció solar per mes"
          subtitle="Energia solar mitjana al dia (MWh)."
          conclusion="L'estiu és quan hi ha més excedent i, per tant, més feina (i més valor) per a la bateria."
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.monthly} margin={{ top: 8, right: 8, bottom: 4, left: -8 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="month" tickLine={false} interval={0} tick={{ fontSize: 10 }} />
              <YAxis tickLine={false} axisLine={false} unit=" MWh" width={46} />
              <Tooltip
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? <TooltipBox title={String(label)} rows={[{ label: "Solar/dia", value: `${nf(Number(payload[0].value), 2)} MWh`, color: C.solar }]} /> : null
                }
              />
              <Bar dataKey="pv_mwh_day" fill={C.solar} radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <Card className="mt-6 p-5">
        <h3 className="text-[15px] font-semibold text-ink">L'excedent solar: regalat o guardat</h3>
        <p className="mt-0.5 text-[13px] text-ink-secondary">Excedent solar diari (producció per sobre del consum) a les dades del campus.</p>
        <div className="mt-4 space-y-3">
          <RescueBar label="Sense bateria (es regala)" value={s.export_base_kwh_day} max={s.export_base_kwh_day} color={C.axis} note="a 0 € i sense estalvi de CO₂" />
          <RescueBar label="Es perd amb la bateria" value={s.export_v8_solar_day} max={s.export_base_kwh_day} color={C.good} note={`${nf(s.export_rescued_pct, 0)} % aprofitat`} />
        </div>
        <p className="mt-4 text-[13px] leading-snug text-ink-secondary">
          La bateria de 6 MWh carrega a migdia amb l'excedent (energia gratis i neta) i el fa servir al vespre: converteix
          energia que es regalaria en estalvi de factura i de CO₂.
        </p>
      </Card>

      <div className="mt-6">
        <Decision>
          Prioritzar <b>carregar amb l'excedent solar de migdia</b> (gratis i net) i descarregar al pic del vespre. Amb la bateria
          gran, gairebé tot l'excedent que abans es regalava ara s'aprofita.
        </Decision>
      </div>
    </div>
  );
}

function RescueBar({ label, value, max, color, note }: { label: string; value: number; max: number; color: string; note: string }) {
  const w = Math.max((value / max) * 100, 1.5);
  return (
    <div className="flex items-center gap-3">
      <div className="w-48 shrink-0 text-right text-[13px] text-ink-secondary">{label}</div>
      <div className="relative h-6 flex-1 rounded bg-black/[0.04]">
        <div className="flex h-full items-center rounded px-2" style={{ width: `${w}%`, background: color }}>
          {w > 14 && <span className="tabular text-[12px] font-semibold text-white">{nf(value)} kWh</span>}
        </div>
        {w <= 14 && <span className="absolute left-[calc(1.5%+6px)] top-1/2 -translate-y-1/2 tabular text-[12px] font-semibold text-ink">{nf(value)} kWh</span>}
      </div>
      <span className="w-40 shrink-0 text-[11px] text-ink-muted">{note}</span>
    </div>
  );
}
