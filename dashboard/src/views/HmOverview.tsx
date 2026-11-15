import { useHmKpis, useHmMeta } from "../lib/data";
import { AnimatedNumber, Card, Decision, ErrorBox, WelcomeHeader, Kpi, Loading, Pill } from "../components/ui";
import { nf, pct } from "../lib/format";
import { C } from "../lib/theme";

const go = (v: string) => {
  window.location.hash = `#/decisio/hm/${v}`;
  window.scrollTo({ top: 0 });
};

export default function HmOverview() {
  const { data: k, isLoading, error } = useHmKpis();
  const { data: m } = useHmMeta();
  if (isLoading || !k) return error ? <ErrorBox error={error} /> : <Loading />;

  return (
    <div>
      <WelcomeHeader
        name="Zoe"
        role="Direcció · UPC Sostenible"
        accent={C.orange}
        subtitle="Bateria del Campus Nord · bateria ampliada (6 MWh)"
      />

      <Card className="mb-6 overflow-hidden">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wide text-orange">L'agent</div>
            <h3 className="mt-1 text-xl font-bold text-ink">Redueix emissions aprofitant la solar, sola</h3>
            <p className="mt-1 max-w-xl text-[14px] leading-snug text-ink-secondary">
              Amb 6 MWh i molta més solar, l'agent preveu i decideix cada hora: emmagatzema l'excedent solar del migdia i
              el fa servir als pics. Funciona sol i no ha comès <b>cap acció impossible</b>.
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

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi value={pct(k.agent_co2_pct, 1)} label="menys CO₂ que sense bateria" sub="pes del 70 % a la puntuació" tone="co2" delay={0} onClick={() => go("estrategia")} />
        <Kpi value={pct(k.agent_cost_pct, 1)} label="menys cost a la factura" sub="pes del 30 %" tone="money" delay={70} onClick={() => go("estrategia")} />
        <Kpi value={pct(k.export_rescued_pct, 0)} label="de l'excedent solar aprofitat" sub="la bateria el guarda en lloc de regalar-lo" tone="solar" delay={140} onClick={() => go("solar")} />
        <Kpi value={pct(k.surplus_hours_pct, 0)} label="d'hores amb excedent solar" sub="producció per sobre del consum" tone="accent" delay={210} onClick={() => go("solar")} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Què guanya aquesta instal·lació</h3>
          <div className="mt-3 space-y-3 text-[13px] leading-snug text-ink-secondary">
            <div className="rounded-lg bg-plane px-3 py-2.5">
              <div className="font-semibold text-ink">Aprofita l'excedent solar</div>
              Amb una solar {m ? "×" + nf(m.solar_factor, 0) : "×12"} més gran, al migdia sobra energia. En lloc de regalar-la a
              la xarxa, la bateria gran la guarda i la fa servir als pics del vespre: se'n recupera el{" "}
              <b>{pct(k.export_rescued_pct, 0)}</b>.
            </div>
            <div className="rounded-lg bg-plane px-3 py-2.5">
              <div className="font-semibold text-ink">Decideix amb previsió pròpia</div>
              Només es coneixen el preu i el CO₂ de les 3 hores vinents; la resta del dia l'agent el <b>preveu</b> (preu, CO₂,
              solar i consum) per decidir quan carregar i quan descarregar.
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Dos riscos que la gestió evita</h3>
          <div className="mt-3 space-y-3 text-[13px] leading-snug text-ink-secondary">
            <div className="rounded-lg bg-plane px-3 py-2.5">
              <div className="font-semibold text-ink">Descarregar a cegues és tirar energia</div>
              La bateria dona 1.500 kW però el campus en consumeix entre 600 i 1.300 (i menys amb sol). El que es descarrega de més es
              vessa a la xarxa sense cobrar ni estalviar CO₂, així que la descàrrega es limita al consum real.
            </div>
            <div className="rounded-lg bg-plane px-3 py-2.5">
              <div className="font-semibold text-ink">Previsió amb marge</div>
              La previsió s'equivoca; per això es carrega una mica de més i es descarrega una mica de menys, per no perdre excedent
              gratuït ni tirar energia als pics.
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Decision>
          Amb més bateria i més solar, el valor es mou cap a <b>aprofitar l'excedent solar</b> i <b>preveure bé</b>. Les pàgines
          següents mostren quant val cada cosa i com es comporta la previsió.
        </Decision>
        <div className="mt-2 flex items-center justify-center gap-2 text-[12px] text-ink-muted">
          <Pill tone="good">{k.infractions} infraccions</Pill>
          <span>·</span>
          <span>període mesurat: {nf(k.validation_hours)} h ({k.validation_start} → {k.validation_end})</span>
        </div>
      </div>
    </div>
  );
}

