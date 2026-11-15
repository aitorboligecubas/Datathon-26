import type { ReactNode } from "react";
import type { Meta } from "../lib/data";

const base = import.meta.env.BASE_URL;

export default function Landing({ enter, meta }: { enter: (p: "decisio" | "operacio") => void; meta?: Meta }) {
  return (
    <div className="min-h-screen bg-plane">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
        <div className="mb-8 flex items-center gap-3">
          <img src={`${base}brand/upc.png`} alt="Universitat Politècnica de Catalunya" className="h-11 w-11" />
          <div>
            <div className="text-[15px] font-semibold text-ink">Bateria del Campus Nord</div>
            <div className="text-[12px] text-ink-muted">UPC Sostenible · Campus Nord</div>
          </div>
        </div>

        {/* Hero */}
        <div className="relative overflow-hidden rounded-2xl border border-black/10 shadow-card">
          <img src={`${base}campus/hero.jpg`} alt="Campus Nord de la UPC" className="h-52 w-full object-cover sm:h-64" />
          <div className="absolute inset-0" style={{ background: "linear-gradient(90deg, rgba(10,12,16,0.85) 0%, rgba(10,12,16,0.5) 50%, rgba(10,12,16,0.1) 100%)" }} />
          <div className="absolute inset-0 flex flex-col justify-end p-6">
            <h1 className="max-w-2xl text-3xl font-bold leading-tight text-white drop-shadow-sm">
              Gestió intel·ligent de la bateria del Campus Nord
            </h1>
            <p className="mt-2 max-w-2xl text-[15px] leading-snug text-white/85">
              Un dashboard per decidir i operar l'emmagatzematge d'energia del campus: menys CO₂, menys factura, zero infraccions.
            </p>
          </div>
          <div className="absolute bottom-1 right-2 text-[9px] text-white/55">Campus Nord UPC · Wikimedia Commons, CC BY 4.0</div>
        </div>

        <p className="mt-8 text-center text-[13px] font-medium uppercase tracking-wide text-ink-muted">Tria la teva perspectiva</p>

        {/* Dues targetes de rol */}
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          <RoleCard
            accent="#007bc0"
            icon={<path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2zM9 20h6M10 22h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />}
            kicker="Direcció i Sostenibilitat"
            title="Decidir"
            desc="Val la pena la bateria? Quina mida? Gestionar-la per emissions o per preu? L'argument d'inversió i impacte, amb dades."
            bullets={["Com va l'agent i quant estalvia", "CO₂ i € estalviats · dimensionat", "Objectiu i gestió de la bateria"]}
            cta="Entrar com a direcció"
            onClick={() => enter("decisio")}
          />
          <RoleCard
            accent="#eb6834"
            icon={<path d="M3 12a9 9 0 0 1 18 0M12 12l4-2M12 12a1.5 1.5 0 1 0 0 .01M5 19h14" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />}
            kicker="Operació del campus"
            title="Operar"
            desc="Què fa la bateria ara, el pla d'avui, l'estalvi de la setmana i els avisos. El monitoratge del dia a dia."
            bullets={["Estat i càrrega en temps real", "Pla d'avui i balanç setmanal", "Avisos de sensors i previsió"]}
            cta="Entrar com a operació"
            onClick={() => enter("operacio")}
          />
        </div>

        <p className="mt-8 text-center text-[11px] text-ink-muted">
          Dins de cada perspectiva pots alternar entre la <b>bateria estàndard</b> (2 MWh) i l'<b>ampliada</b> (6 MWh).
          {meta && <> · Dades {meta.data_source} · {meta.train_start} → {meta.train_end}</>}
        </p>
        <p className="mt-1 text-center text-[11px] text-ink-muted">Universitat Politècnica de Catalunya · BarcelonaTech</p>
      </div>
    </div>
  );
}

function RoleCard({
  accent, icon, kicker, title, desc, bullets, cta, onClick,
}: {
  accent: string;
  icon: ReactNode;
  kicker: string;
  title: string;
  desc: string;
  bullets: string[];
  cta: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="animate-pop group flex flex-col rounded-2xl border border-black/10 bg-surface p-6 text-left shadow-card transition duration-200 hover:-translate-y-1 hover:shadow-md"
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-xl text-white" style={{ background: accent }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">{icon}</svg>
      </span>
      <div className="mt-4 text-[12px] font-semibold uppercase tracking-wide" style={{ color: accent }}>{kicker}</div>
      <div className="mt-0.5 text-2xl font-bold text-ink">{title}</div>
      <p className="mt-2 text-[14px] leading-snug text-ink-secondary">{desc}</p>
      <ul className="mt-3 space-y-1 text-[13px] text-ink-secondary">
        {bullets.map((b, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: accent }} />
            {b}
          </li>
        ))}
      </ul>
      <span className="mt-5 inline-flex items-center gap-1.5 text-[14px] font-semibold transition-transform group-hover:translate-x-0.5" style={{ color: accent }}>
        {cta}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
    </button>
  );
}
