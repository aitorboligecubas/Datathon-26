import { useEffect, useState } from "react";
import { useMeta } from "./lib/data";
import Overview from "./views/Overview";
import CampusMap from "./views/CampusMap";
import Patterns from "./views/Patterns";
import Objective from "./views/Objective";
import Strategy from "./views/Strategy";
import Sizing from "./views/Sizing";
import Quality from "./views/Quality";
import HmOverview from "./views/HmOverview";
import HmSolar from "./views/HmSolar";
import HmForecast from "./views/HmForecast";
import HmStrategy from "./views/HmStrategy";
import HmData from "./views/HmData";
import OpsToday from "./views/OpsToday";
import GeneralInfo from "./views/GeneralInfo";
import Landing from "./views/Landing";

const GENERAL: NavItem = { id: "general", short: "Challenge data", title: "Challenge data", question: "Comparatives i context del repte", Component: GeneralInfo };

type Mode = "st" | "hm";
type Persp = "decisio" | "operacio";

interface NavItem {
  id: string;
  short: string;
  title: string;
  question: string;
  Component: (p: { mode: Mode }) => JSX.Element;
}

// Perspectiva DECISIÓ (direcció i sostenibilitat): el dashboard estratègic.
const DECISIO: Record<Mode, NavItem[]> = {
  st: [
    { id: "resum", short: "Resum", title: "Resum executiu", question: "Val la pena la bateria?", Component: Overview },
    { id: "xarxa", short: "La xarxa", title: "Quan contamina i costa la xarxa", question: "Quan carregar i descarregar?", Component: Patterns },
    { id: "objectiu", short: "Objectiu", title: "CO₂, cost o 70/30?", question: "Què ha d'optimitzar l'agent?", Component: Objective },
    { id: "estrategia", short: "Estratègia", title: "Funciona la nostra estratègia?", question: "És bo el nostre agent?", Component: Strategy },
    { id: "dimensionat", short: "Dimensionat", title: "Quina mida de bateria?", question: "1, 2, 4 o 8 MWh?", Component: Sizing },
    { id: "dades", short: "Dades", title: "Ens podem fiar de les dades?", question: "Són fiables els números?", Component: Quality },
    GENERAL,
  ],
  hm: [
    { id: "resum", short: "Resum", title: "Bateria ampliada: resum", question: "Com rendeix la instal·lació?", Component: HmOverview },
    { id: "solar", short: "La solar", title: "La solar ara compta (12×)", question: "Com aprofitar l'excedent?", Component: HmSolar },
    { id: "previsio", short: "La previsió", title: "Preveure el futur", question: "Quant val preveure?", Component: HmForecast },
    { id: "estrategia", short: "Estratègia", title: "La nostra estratègia", question: "És bo el nostre agent?", Component: HmStrategy },
    { id: "dades", short: "Dades", title: "Dades i qualitat", question: "Meteo i qualitat de dades", Component: HmData },
    GENERAL,
  ],
};

// Perspectiva OPERACIÓ (equip del campus): monitoratge del dia a dia.
function operacio(_mode: Mode): NavItem[] {
  return [
    { id: "avui", short: "Avui", title: "Monitoratge de la bateria", question: "Què fa la bateria ara?", Component: OpsToday },
    { id: "campus", short: "El campus", title: "On està connectada la bateria", question: "On és la bateria?", Component: CampusMap },
    GENERAL,
  ];
}

function navFor(persp: Persp, mode: Mode): NavItem[] {
  return persp === "operacio" ? operacio(mode) : DECISIO[mode];
}

const MODE_LABEL: Record<Mode, { name: string; tag: string }> = {
  st: { name: "Estàndard", tag: "2 MWh" },
  hm: { name: "Ampliada", tag: "6 MWh" },
};
const PERSP_LABEL: Record<Persp, { name: string; tag: string }> = {
  decisio: { name: "Decisió", tag: "DIR" },
  operacio: { name: "Operació", tag: "OPS" },
};

const ICON: Record<string, string> = {
  resum: "M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10",
  campus: "M12 21s-7-5.2-7-11a7 7 0 1 1 14 0c0 5.8-7 11-7 11zM12 10a2 2 0 1 0 0-.01",
  xarxa: "M3 17l5-6 4 3 5-8M3 21h18",
  objectiu: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 12m-5 0a5 5 0 1 0 10 0a5 5 0 1 0-10 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0",
  estrategia: "M5 19l7-14 7 14M5 19c2-1.5 5-1.5 7 0 2 1.5 5 1.5 7 0",
  dimensionat: "M4 7h16M4 12h16M4 17h10",
  dades: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  solar: "M12 3v2M12 19v2M5 12H3M21 12h-2M6 6l-1.4-1.4M19.4 19.4L18 18M18 6l1.4-1.4M4.6 19.4L6 18M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
  previsio: "M3 12s3.5-7 9-7 9 7 9 7-3.5 7-9 7-9-7-9-7zM12 12m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0",
  avui: "M3 12h4l2-7 4 14 2-7h6",
  sensors: "M12 3a9 9 0 1 0 9 9M12 12l5-3M12 12a1.5 1.5 0 1 0 .01 0",
  general: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 8h.01M11 12h1v4h1",
};

function NavIcon({ id }: { id: string }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d={ICON[id] ?? ICON.resum} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

interface Route {
  landing: boolean;
  persp: Persp;
  mode: Mode;
  view: string;
}

function parseHash(): Route {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts.length === 0) return { landing: true, persp: "decisio", mode: "st", view: "resum" };
  const persp: Persp = parts[0] === "operacio" ? "operacio" : "decisio";
  const mode: Mode = parts[1] === "hm" ? "hm" : "st";
  let view = parts[2] ?? "";
  const nav = navFor(persp, mode);
  if (!nav.some((n) => n.id === view)) view = nav[0].id;
  return { landing: false, persp, mode, view };
}

function useRoute() {
  const [route, setRoute] = useState(parseHash);
  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = (persp: Persp, mode: Mode, view: string) => {
    window.location.hash = `#/${persp}/${mode}/${view}`;
    window.scrollTo({ top: 0 });
  };
  const goLanding = () => {
    window.location.hash = "#/";
    window.scrollTo({ top: 0 });
  };
  return { ...route, go, goLanding };
}

export default function App() {
  const { landing, persp, mode, view, go, goLanding } = useRoute();
  const { data: meta } = useMeta();

  if (landing) return <Landing meta={meta} enter={(p) => go(p, "st", p === "operacio" ? "avui" : "resum")} />;

  const nav = navFor(persp, mode);
  const active = nav.find((n) => n.id === view) ?? nav[0];
  const idx = nav.findIndex((n) => n.id === active.id);
  const accent = mode === "hm" ? "#eb6834" : "#007bc0";
  const firstView = (p: Persp) => (p === "operacio" ? "avui" : "resum");

  return (
    <div className="min-h-full lg:flex">
      <aside className="z-10 border-b border-black/[0.06] bg-white/80 backdrop-blur lg:sticky lg:top-0 lg:h-screen lg:w-72 lg:shrink-0 lg:overflow-y-auto lg:border-b-0 lg:border-r">
        <button onClick={goLanding} className="flex w-full items-center gap-2.5 px-5 pb-4 pt-5 text-left transition-colors hover:bg-black/[0.02]">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-soft ring-1 ring-black/[0.05]">
            <img src={`${import.meta.env.BASE_URL}brand/upc.png`} alt="Universitat Politècnica de Catalunya" className="h-7 w-7" />
          </span>
          <div>
            <div className="text-[13px] font-semibold leading-tight text-ink">Bateria del Campus Nord</div>
            <div className="text-[11px] leading-tight text-ink-muted">UPC Sostenible · Campus Nord</div>
          </div>
        </button>

        {/* Perspectiva */}
        <div className="px-4 pb-2">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Perspectiva</div>
          <div className="flex rounded-full bg-black/[0.04] p-1">
            {(["decisio", "operacio"] as Persp[]).map((pk) => (
              <button
                key={pk}
                onClick={() => go(pk, mode, firstView(pk))}
                className={`flex-1 rounded-full px-2 py-1.5 text-[12px] font-semibold transition-colors ${persp === pk ? "text-white shadow-sm" : "text-ink-secondary hover:text-ink"}`}
                style={persp === pk ? { background: accent } : undefined}
              >
                {PERSP_LABEL[pk].name}
              </button>
            ))}
          </div>
        </div>

        {/* Instal·lació */}
        <div className="px-4 pb-3">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">Instal·lació</div>
          <div className="flex rounded-full bg-black/[0.04] p-1">
            {(["st", "hm"] as Mode[]).map((mk) => (
              <button
                key={mk}
                onClick={() => go(persp, mk, view)}
                className={`flex-1 rounded-full px-2 py-1.5 text-[12px] font-semibold transition-colors ${mode === mk ? "text-white shadow-sm" : "text-ink-secondary hover:text-ink"}`}
                style={mode === mk ? { background: mk === "hm" ? "#eb6834" : "#007bc0" } : undefined}
              >
                {MODE_LABEL[mk].name}
              </button>
            ))}
          </div>
          <p className="mt-2 text-[10px] leading-tight text-ink-muted">
            {mode === "hm" ? "Bateria ampliada: 6 MWh · ±1.500 kW · 12× solar." : "Bateria estàndard: 2 MWh · ±500 kW."}
          </p>
        </div>

        <nav className="flex gap-1.5 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
          {nav.filter((n) => n.id !== "general").map((n) => {
            const isActive = n.id === active.id;
            return (
              <button
                key={n.id}
                onClick={() => go(persp, mode, n.id)}
                className={`group flex shrink-0 items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-all lg:w-full ${isActive ? "shadow-soft" : "hover:bg-black/[0.03]"}`}
                style={isActive ? { background: accent } : undefined}
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors" style={isActive ? { background: "rgba(255,255,255,0.22)", color: "#fff" } : { background: "rgba(0,0,0,0.05)", color: "#52514e" }}>
                  <NavIcon id={n.id} />
                </span>
                <span className="min-w-0">
                  <span className={`block text-[13px] font-semibold leading-tight ${isActive ? "text-white" : "text-ink"}`}>{n.short}</span>
                  <span className={`hidden text-[11px] leading-tight lg:block ${isActive ? "text-white/75" : "text-ink-muted"}`}>{n.question}</span>
                </span>
              </button>
            );
          })}

          {/* Challenge data: a part, al fons (material per al jurat, no per a l'operació diària) */}
          <div className="shrink-0 lg:mt-2 lg:border-t lg:border-black/[0.06] lg:pt-2">
            {(() => {
              const isActive = active.id === "general";
              return (
                <button
                  onClick={() => go(persp, mode, "general")}
                  className={`group flex shrink-0 items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-all lg:w-full ${isActive ? "shadow-soft" : "opacity-70 hover:bg-black/[0.03] hover:opacity-100"}`}
                  style={isActive ? { background: accent } : undefined}
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors" style={isActive ? { background: "rgba(255,255,255,0.22)", color: "#fff" } : { background: "rgba(0,0,0,0.05)", color: "#52514e" }}>
                    <NavIcon id="general" />
                  </span>
                  <span className="min-w-0">
                    <span className={`block text-[13px] font-semibold leading-tight ${isActive ? "text-white" : "text-ink-secondary"}`}>Challenge data</span>
                    <span className={`hidden text-[11px] leading-tight lg:block ${isActive ? "text-white/75" : "text-ink-muted"}`}>Comparatives i context del repte</span>
                  </span>
                </button>
              );
            })()}
          </div>
        </nav>

        <div className="hidden px-5 py-4 lg:block">
          <button onClick={goLanding} className="text-[11px] font-medium text-ink-muted transition-colors hover:text-ink">← Tornar a l'inici</button>
          <p className="mt-2 text-[11px] leading-relaxed text-ink-muted">
            Totes les xifres surten de les dades reals del Campus Nord.
            {meta && <> Dades {meta.data_source} · {meta.train_start} → {meta.train_end}.</>}
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-9">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px] font-medium" style={{ color: accent }}>
            <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white" style={{ background: persp === "operacio" ? "#52514e" : accent }}>
              {PERSP_LABEL[persp].name}
            </span>
            <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white" style={{ background: accent }}>
              {MODE_LABEL[mode].tag}
            </span>
            <span className="tabular">{idx + 1} / {nav.length}</span>
            <span className="text-ink-muted">·</span>
            <span className="text-ink-muted">{active.question}</span>
          </div>
          <div key={`${persp}/${mode}/${active.id}`} className="animate-view">
            <active.Component mode={mode} />
          </div>

          <div className="mt-10 flex items-center justify-between border-t border-hair pt-5">
            <NavButton item={nav[idx - 1]} dir="prev" persp={persp} mode={mode} go={go} accent={accent} />
            <NavButton item={nav[idx + 1]} dir="next" persp={persp} mode={mode} go={go} accent={accent} />
          </div>
          <footer className="mt-6 space-y-0.5 text-center text-[11px] text-ink-muted">
            <div>Gestió de la bateria del Campus Nord · {PERSP_LABEL[persp].name} · {MODE_LABEL[mode].name} · generat {meta?.generated ?? "…"}</div>
            <div>Universitat Politècnica de Catalunya · BarcelonaTech · imatges del Campus Nord: Wikimedia Commons (CC BY / CC BY-SA)</div>
          </footer>
        </div>
      </main>
    </div>
  );
}

function NavButton({ item, dir, persp, mode, go, accent }: { item?: NavItem; dir: "prev" | "next"; persp: Persp; mode: Mode; go: (p: Persp, m: Mode, v: string) => void; accent: string }) {
  if (!item) return <span />;
  return (
    <button onClick={() => go(persp, mode, item.id)} className={`flex max-w-[48%] flex-col ${dir === "next" ? "items-end text-right" : "items-start text-left"}`}>
      <span className="text-[11px] text-ink-muted">{dir === "prev" ? "← Anterior" : "Següent →"}</span>
      <span className="text-[13px] font-medium" style={{ color: accent }}>{item.title}</span>
    </button>
  );
}
