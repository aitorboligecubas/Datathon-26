import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useKpis } from "../lib/data";
import { Card, Decision, ErrorBox, HeroBanner, Pill } from "../components/ui";
import { C, HEAT_RAMP, rampColor } from "../lib/theme";
import { nf } from "../lib/format";
import { CAMPUS_CENTER, TYPE_LABEL, ZONE_BY_ID, ZONES, zoneIdForBuilding } from "../data/campus";

const MAX_SHARE = Math.max(...ZONES.map((z) => z.share));
const heatOf = (share: number) => rampColor(HEAT_RAMP, share / MAX_SHARE);
const base = import.meta.env.BASE_URL;
const BATTERY_LNGLAT: [number, number] = [2.1155, 41.38963];

export default function CampusMap() {
  const { data: k, error } = useKpis();
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const homeRef = useRef<{ center: [number, number]; zoom: number; bearing: number; pitch: number } | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [pinnedId, setPinnedId] = useState<string | null>("bsc");

  const resetView = () => {
    const m = mapRef.current;
    const h = homeRef.current;
    if (m && h) m.easeTo({ center: h.center, zoom: h.zoom, bearing: h.bearing, pitch: h.pitch, duration: 650 });
  };

  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapEl.current,
      center: [CAMPUS_CENTER[1], CAMPUS_CENTER[0]], // maplibre vol [lng, lat]
      zoom: 15.4,
      pitch: 55,
      bearing: -18,
      scrollZoom: false,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
          },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#edece7" } },
          // Entorn (no-UPC) en gris: saturació -1 = escala de grisos
          { id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -1, "raster-opacity": 0.92, "raster-contrast": 0.05 } },
        ],
      },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    fetch(`${base}data/campus_buildings.geojson`)
      .then((r) => r.json())
      .then((gj) => {
        // Afegeix les capes quan l'estil estigui a punt (sense dependre de l'event "load",
        // que en alguns entorns triga per la càrrega de tessel·les).
        const install = () => {
          if (!mapRef.current) return;
          if (!map.isStyleLoaded()) {
            setTimeout(install, 80);
            return;
          }
          let minLng = 180, minLat = 90, maxLng = -180, maxLat = -90;
          gj.features.forEach((f: any, i: number) => {
            f.id = i;
            const zid = zoneIdForBuilding(f.properties?.name ?? "");
            if (zid) {
              const z = ZONE_BY_ID[zid];
              f.properties.zoneId = zid;
              f.properties.color = heatOf(z.share);
              f.properties.height = 14 + (z.share / MAX_SHARE) * 74; // alçada ∝ consum estimat
              f.properties.upc = 1;
              for (const [lng, lat] of f.geometry.coordinates[0]) {
                minLng = Math.min(minLng, lng); maxLng = Math.max(maxLng, lng);
                minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
              }
            } else {
              f.properties.zoneId = "";
              f.properties.color = "#c7c6c0";
              f.properties.height = 8;
              f.properties.upc = 0;
            }
          });
          map.addSource("buildings", { type: "geojson", data: gj });
          map.addLayer({
            id: "b-context",
            type: "fill-extrusion",
            source: "buildings",
            filter: ["==", ["get", "upc"], 0],
            paint: { "fill-extrusion-color": "#c7c6c0", "fill-extrusion-height": ["get", "height"], "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.5 },
          });
          map.addLayer({
            id: "b-upc",
            type: "fill-extrusion",
            source: "buildings",
            filter: ["==", ["get", "upc"], 1],
            paint: {
              "fill-extrusion-color": ["get", "color"],
              "fill-extrusion-height": ["case", ["boolean", ["feature-state", "hover"], false], ["+", ["get", "height"], 18], ["get", "height"]],
              "fill-extrusion-base": 0,
              "fill-extrusion-opacity": 0.92,
            },
          });
          map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 56, bearing: -18, pitch: 55, duration: 0, maxZoom: 17 });
          // Vista d'inici (per al botó de reinici) i restriccions: el mapa no surt del campus.
          homeRef.current = { center: map.getCenter().toArray() as [number, number], zoom: map.getZoom(), bearing: -18, pitch: 55 };
          map.setMinZoom(map.getZoom() - 0.25); // no es pot allunyar més que la vista general
          map.setMaxZoom(19);
          const pad = 0.002; // ~180 m de marge al voltant del campus
          map.setMaxBounds([[minLng - pad, minLat - pad], [maxLng + pad, maxLat + pad]]);

          const el = document.createElement("div");
          el.innerHTML = `<div style="display:flex;align-items:center;gap:6px">
            <span style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:9999px;background:#fff;border:2.5px solid ${C.upc};box-shadow:0 2px 5px rgba(0,0,0,.3)">
              <svg width="15" height="13" viewBox="0 0 15 13" fill="none"><rect x="0.8" y="1" width="11" height="10" rx="2" stroke="${C.upc}" stroke-width="1.6"/><rect x="12" y="4" width="2" height="4" rx="1" fill="${C.upc}"/><path d="M6 2 4 5.5h2.2L5 9l3.2-4.2H6z" fill="${C.orange}"/></svg>
            </span>
            <span style="white-space:nowrap;font:600 12px system-ui;color:${C.upc};background:rgba(255,255,255,.9);padding:1px 6px;border-radius:5px;box-shadow:0 1px 2px rgba(0,0,0,.15)">Bateria proposada</span>
          </div>`;
          new maplibregl.Marker({ element: el, anchor: "left" }).setLngLat(BATTERY_LNGLAT).addTo(map);

          let hovered: number | null = null;
          let clearTimer: ReturnType<typeof setTimeout> | null = null;
          const clearHover = () => {
            if (hovered !== null) map.setFeatureState({ source: "buildings", id: hovered }, { hover: false });
            hovered = null;
          };
          map.on("mousemove", "b-upc", (e) => {
            const f = e.features?.[0];
            if (!f) return;
            if (clearTimer) { clearTimeout(clearTimer); clearTimer = null; } // cancel·la l'esborrat pendent en creuar entre edificis
            map.getCanvas().style.cursor = "pointer";
            if (hovered !== f.id) {
              clearHover();
              hovered = f.id as number;
              map.setFeatureState({ source: "buildings", id: hovered }, { hover: true });
            }
            setHoverId((f.properties as any).zoneId || null);
          });
          map.on("mouseleave", "b-upc", () => {
            map.getCanvas().style.cursor = "";
            clearHover();
            // retard petit: evita el parpelleig del panell en passar d'un edifici a un altre
            if (clearTimer) clearTimeout(clearTimer);
            clearTimer = setTimeout(() => setHoverId(null), 160);
          });
          map.on("click", "b-upc", (e) => {
            const zid = (e.features?.[0]?.properties as any)?.zoneId;
            if (zid) setPinnedId((p) => (p === zid ? null : zid));
          });
          map.resize();
        };
        install();
      });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  if (error) return <ErrorBox error={error} />;

  const totalAvgKw = k ? (k.annual_baseline.mwh_day * 1000) / 24 : 0;
  const mwhDay = k?.annual_baseline.mwh_day ?? 0;
  const activeId = hoverId ?? pinnedId;
  const active = activeId ? ZONE_BY_ID[activeId] : null;
  const kwOf = (share: number) => Math.round((share * totalAvgKw) / 10) * 10; // arrodonit a 10 kW: és un repartiment modelat, no una mesura
  const ranked = [...ZONES].sort((a, b) => b.share - a.share);

  return (
    <div>
      <HeroBanner
        image="campus/vertex.jpg"
        badge="Campus Nord · UPC"
        accent="#007bc0"
        title="On es consumeix l'energia al campus?"
        lead="Mapa 3D real del Campus Nord: cada edifici s'eleva i s'acoloreix segons la intensitat de consum estimada. Passa el ratolí per sobre d'un edifici (o clica'l) per veure'n el detall i decidir on connectar la bateria."
        credit="Edifici Vèrtex, Campus Nord UPC · Wikimedia Commons, CC BY-SA 3.0"
      />

      <div className="mb-5 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/[0.08] px-4 py-2.5 text-[12px] leading-snug text-[#7a5200]">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="mt-0.5 shrink-0" aria-hidden="true">
          <path d="M12 9v4m0 4h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>
          <b>Repartiment estimat, il·lustratiu.</b> El dataset només mesura el consum <b>total</b> del campus
          ({nf(mwhDay, 1)} MWh/dia, ~{nf(totalAvgKw)} kW de mitjana), no el desglossa per edifici. Les traces reals
          dels edificis són d'OpenStreetMap; el color i l'alçada <b>relativa</b> són una modelització del consum.
          Les xifres per edifici són <b>orientatives</b>, no mesures reals.
        </span>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Card className="overflow-hidden p-0">
          <div className="flex items-center justify-between px-4 pt-3">
            <h3 className="text-[15px] font-semibold text-ink">Mapa 3D de consum · Campus Nord</h3>
            <HeatLegend />
          </div>
          <div className="relative mt-3">
            <div ref={mapEl} className="h-[500px] w-full" style={{ background: "#edece7" }} />
            <button
              onClick={resetView}
              className="absolute right-3 top-3 flex items-center gap-1.5 rounded-lg border border-black/10 bg-surface/95 px-2.5 py-1.5 text-[12px] font-medium text-ink shadow-card backdrop-blur transition-colors hover:bg-surface"
              title="Tornar a la vista general del campus"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M3 9V5a2 2 0 0 1 2-2h4M21 9V5a2 2 0 0 0-2-2h-4M3 15v4a2 2 0 0 0 2 2h4M21 15v4a2 2 0 0 1-2 2h-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Vista general
            </button>
          </div>
          <p className="px-4 py-2 text-[11px] text-ink-muted">
            Edificis d'OpenStreetMap; més alt i més vermell = més consum estimat. L'entorn (no-UPC) es mostra en gris.
          </p>
        </Card>

        <div className="flex flex-col gap-4">
          <Card className="p-5">
            {active ? (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-wide text-upc">{TYPE_LABEL[active.type]}</div>
                    <h3 className="mt-0.5 text-[17px] font-bold leading-tight text-ink">{active.name}</h3>
                  </div>
                  <span className="mt-1 h-4 w-4 shrink-0 rounded" style={{ background: heatOf(active.share) }} />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <Metric value={`~${nf(kwOf(active.share))} kW`} label="consum mitjà estimat" />
                  <Metric value={`~${nf(active.share * 100, 0)} %`} label="del consum del campus" />
                  <Metric value={`~${nf(active.share * mwhDay, 1)} MWh`} label="al dia (estimat)" />
                  <Metric value={active.constant ? "Plana 24 h" : "Horari"} label="perfil de càrrega" />
                </div>
                <p className="mt-4 text-[13px] leading-snug text-ink-secondary">{active.note}</p>
                {active.constant && (
                  <div className="mt-3">
                    <Pill tone="good">Bona candidata per a la bateria</Pill>
                  </div>
                )}
                <p className="mt-4 text-[11px] text-ink-muted">
                  {pinnedId === active.id ? "Fixada (clica de nou per deixar-la anar)." : "Clica l'edifici per fixar-lo."}
                </p>
              </>
            ) : (
              <p className="text-[14px] text-ink-secondary">Passa el ratolí per un edifici del mapa per veure'n el detall.</p>
            )}
          </Card>

          <Card className="p-5">
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-[14px] font-semibold text-ink">Zones per consum estimat</h3>
              <span className="flex items-center gap-1 text-[10px] text-ink-muted">
                <BatteryIcon className="h-3 w-3 text-good" />
                bona candidata
              </span>
            </div>
            {/* Llista només de lectura: la selecció es controla des del mapa (evita el parpelleig en passar el ratolí per les barres) */}
            <div className="mt-3 space-y-1.5">
              {ranked.map((z) => {
                const w = (z.share / MAX_SHARE) * 100;
                const isActive = z.id === activeId;
                return (
                  <div key={z.id} className="flex w-full items-center gap-2 text-left">
                    <span className="flex w-3.5 shrink-0 justify-center" title={z.constant ? "Bona candidata per a la bateria" : undefined}>
                      {z.constant && <BatteryIcon className="h-3.5 w-3.5 text-good" />}
                    </span>
                    <span className={`w-[88px] shrink-0 truncate text-[11px] ${isActive ? "font-semibold text-ink" : "text-ink-secondary"}`}>
                      {z.name.split(" · ")[0]}
                    </span>
                    <span className="relative h-4 flex-1 rounded bg-black/[0.04]">
                      <span className="block h-full rounded" style={{ width: `${w}%`, background: heatOf(z.share), outline: isActive ? `1.5px solid ${C.ink}` : "none" }} />
                    </span>
                    <span className="w-14 shrink-0 text-right text-[11px] tabular text-ink-secondary">{nf(kwOf(z.share))} kW</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-6">
        <Decision>
          El perfil de càrrega modelat <b>suggereix situar la bateria a prop del BSC/MareNostrum i del centre de dades</b>:
          serien les càrregues més grans i més <b>constants</b> (24 h) — les torres més altes del mapa —, de manera que la
          bateria sempre tindria consum que cobrir a les hores dolentes i es reduirien pèrdues de transport. Les <b>aules i
          despatxos</b>, en canvi, són càrregues flexibles i estacionals. És una orientació a partir del repartiment estimat,
          a confirmar amb les dades reals per edifici.
        </Decision>
      </div>
    </div>
  );
}

function BatteryIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <rect x="2" y="7" width="16" height="10" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <rect x="20" y="10" width="2" height="4" rx="1" fill="currentColor" />
      <path d="M11 9 8.5 13H11l-1 3 3.2-4.3H11z" fill="currentColor" />
    </svg>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg bg-plane px-3 py-2">
      <div className="text-[18px] font-semibold leading-none tabular text-ink">{value}</div>
      <div className="mt-1 text-[11px] leading-tight text-ink-secondary">{label}</div>
    </div>
  );
}

function HeatLegend() {
  return (
    <div className="flex items-center gap-2 text-[11px] text-ink-muted">
      <span>menys</span>
      <span className="h-2.5 w-24 rounded-full" style={{ background: `linear-gradient(90deg, ${HEAT_RAMP[0]}, ${HEAT_RAMP[3]}, ${HEAT_RAMP[HEAT_RAMP.length - 1]})` }} />
      <span>més consum</span>
    </div>
  );
}
