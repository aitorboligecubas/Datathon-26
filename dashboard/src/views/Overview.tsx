import { useKpis } from "../lib/data";
import { AnimatedNumber, Card, Decision, ErrorBox, WelcomeHeader, Kpi, Loading } from "../components/ui";
import { nf, pct, eurCompact } from "../lib/format";
import { C } from "../lib/theme";

const go = (v: string) => {
  window.location.hash = `#/decisio/st/${v}`;
  window.scrollTo({ top: 0 });
};

export default function Overview() {
  const { data: k, isLoading, error } = useKpis();
  if (isLoading || !k) return error ? <ErrorBox error={error} /> : <Loading />;

  return (
    <div>
      <WelcomeHeader
        name="Zoe"
        role="Direcció · UPC Sostenible"
        accent={C.upc}
        subtitle="Bateria del Campus Nord · bateria estàndard (2 MWh)"
      />

      {/* Estat de l'agent */}
      <Card className="mb-6 overflow-hidden">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wide text-good">L'agent</div>
            <h3 className="mt-1 text-xl font-bold text-ink">Redueix emissions gestionant-se sola</h3>
            <p className="mt-1 max-w-xl text-[14px] leading-snug text-ink-secondary">
              Cada hora l'agent decideix carregar o descarregar segons el CO₂ i el preu de la xarxa. Funciona de forma
              autònoma i no ha comès <b>cap acció impossible</b> en tot el període.
            </p>
          </div>
          <div className="flex shrink-0 items-end gap-2">
            <div className="text-[64px] font-bold leading-none tracking-tight tabular text-co2">
              <AnimatedNumber value={k.agent_co2_pct} decimals={1} />%
            </div>
            <div className="pb-2 text-[13px] leading-tight text-ink-secondary">
              menys CO₂
              <br />
              que sense bateria
            </div>
          </div>
        </div>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={pct(k.agent_co2_pct)} label="CO₂ estalviat" sub="pes del 70 % a la puntuació" tone="co2" delay={0} onClick={() => go("xarxa")} />
        <Kpi value={pct(k.agent_cost_pct)} label="Cost estalviat" sub="pes del 30 %" tone="money" delay={70} onClick={() => go("objectiu")} />
        <Kpi value={`${nf(k.co2_t_year_2mwh)} t`} label="CO₂ evitat l'any" sub="amb la bateria de 2 MWh" tone="co2" delay={140} onClick={() => go("dimensionat")} />
        <Kpi value={eurCompact(k.eur_year_2mwh)} label="Estalvi a la factura" sub="l'any, amb 2 MWh" tone="money" delay={210} onClick={() => go("dimensionat")} />
      </div>

      {/* Contexto del campus */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">El campus, sense bateria (a l'any)</h3>
          <p className="mt-0.5 text-[13px] text-ink-secondary">La referència contra la qual es mesura tot l'estalvi.</p>
          <div className="mt-4 grid grid-cols-3 gap-3 text-center">
            <Stat big={`${nf(k.annual_baseline.gwh, 1)}`} unit="GWh" label="energia comprada" />
            <Stat big={`${nf(k.annual_baseline.co2_t)}`} unit="t CO₂" label="emeses" />
            <Stat big={eurCompact(k.annual_baseline.eur)} unit="" label="de factura" />
          </div>
          <p className="mt-4 text-[13px] leading-snug text-ink-secondary">
            La bateria (2 MWh) és només el <b>{nf((100 * 2) / k.annual_baseline.mwh_day, 1)} %</b> del consum diari ({nf(k.annual_baseline.mwh_day, 1)} MWh).
            Per això l'estalvi es mou al voltant del {nf(k.agent_co2_pct, 0)} %: no és poc ambició, és física.
          </p>
        </Card>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Què prioritza la gestió</h3>
          <div className="mt-3 rounded-lg bg-plane px-4 py-3 text-center text-[15px] text-ink">
            <span className="font-semibold text-co2">70 % CO₂</span> +{" "}
            <span className="font-semibold text-money">30 % cost</span>
          </div>
          <ul className="mt-3 space-y-1.5 text-[13px] leading-snug text-ink-secondary">
            <li>· El <b>CO₂ pesa més que l'euro</b> (70/30): primer descarbonitzar, després estalviar.</li>
            <li>· La bateria carrega a les hores netes i barates, i descarrega a les brutes i cares.</li>
            <li>· Cap acció impossible: <b>{k.infractions} infraccions</b> en tot el període.</li>
            <li>
              · Resultats mesurats sobre <b>{nf(k.validation_hours)} h</b> reals del campus ({k.validation_start} → {k.validation_end}).
            </li>
          </ul>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          Hi ha un cas clar per instal·lar la bateria i gestionar-la amb un planificador. La pregunta ja no és
          «quin algorisme», sinó <b>quina mida</b> i <b>amb quin objectiu</b> — les dues decisions que desglossen les
          pàgines següents.
        </Decision>
      </div>
    </div>
  );
}

function Stat({ big, unit, label }: { big: string; unit: string; label: string }) {
  return (
    <div>
      <div className="text-[22px] font-semibold leading-none tabular text-ink">
        {big}
        {unit && <span className="ml-1 text-[13px] font-normal text-ink-muted">{unit}</span>}
      </div>
      <div className="mt-1 text-[12px] leading-tight text-ink-secondary">{label}</div>
    </div>
  );
}

