"""Auditoría del agente: ¿queda algo que ganar y puede romperse? NO se empaqueta.

Owner: P1 (optimización y robustez).

    python scripts/p1_auditoria.py            # todo (unos 6-8 min)
    python scripts/p1_auditoria.py --quick    # menos episodios y menos fuzzing

Bloques (cada uno responde a una pregunta y escribe su tabla en results/p1_auditoria.md):
1. Calibración: ¿nuestro simulador da lo mismo que el oficial en TODOS los datos, no solo en validación?
2. Episodios tipo test: 12 semanas al azar, concatenadas como el test. ¿A qué distancia del óptimo quedamos?
3. Semana sin datos de contador: un episodio con el calendario del test oficial en el que noviembre viene
   a cero (en el train, noviembre no tiene datos de contador) y Navidad con poco consumo.
   ¿Qué hace nuestro agente, qué hacía antes y qué harían otros planteamientos habituales?
4. Leaderboard público: el score público solo cuenta la mitad de las horas. ¿Cuánto puede moverse el score
   público de un agente por cómo cae esa mitad, sin que el agente sea mejor ni peor?
5. Fuzzing: observaciones hostiles (NaN, listas vacías, tipos raros). ¿Alguna excepción o infracción?
6. Latencia: ¿cuánto tarda cada paso en el peor caso?
"""
import argparse
import importlib.util
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from battery.adapter import make_official_obs  # noqa: E402
from battery.baselines import OracleAgent  # noqa: E402
from battery.data import TRAIN_DIR, ensure_official, is_synthetic, load, train_split, validation_split  # noqa: E402
from battery.optimizer import score_weights  # noqa: E402
from battery.params import DEFAULT_PARAMS as P  # noqa: E402
from battery.policy import BatteryAgent, MPCPolicy  # noqa: E402
from battery.sim import apply_action, baseline_totals, score, simulate, to_env_frame  # noqa: E402

OUT = REPO / "results" / "p1_auditoria.md"
KIT = REPO / "oficial" / "starter_kit"
WEEK = 168


def fmt(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


# ------------------------------------------------------------------ agentes de comparación
class _Wrap:
    def __init__(self, policy):
        self.policy = policy

    def act(self, obs):
        return self.policy.act(obs)


class _NoCap(MPCPolicy):
    """Sin tope de descarga ni seguimiento de semanas: un LP "a secas" con la previsión que se le dé."""

    def cap_discharge(self, action_kw, obs):
        return action_kw

    def track_block(self, obs):
        return False


class _Before(MPCPolicy):
    """Nuestro agente antes de esta auditoría: sin seguimiento de semanas sin datos."""

    def track_block(self, obs):
        return False


class _HugeLoad:
    """Previsión de quien ignora el consumo: supone que siempre hay de sobra."""

    def update(self, obs):
        pass

    def forecast(self, obs, h):
        return np.full(h, 1e6), np.zeros(h)


class _Persistence:
    """Previsión habitual: el consumo de las próximas 24 h será el de la última hora."""

    def __init__(self):
        self.load, self.pv = 1000.0, 0.0

    def update(self, obs):
        if math.isfinite(obs.load_prev_kw):
            self.load = obs.load_prev_kw
        if math.isfinite(obs.pv_prev_kw):
            self.pv = obs.pv_prev_kw

    def forecast(self, obs, h):
        return np.full(h, self.load), np.full(h, self.pv)


class _ProfileOnly:
    """Previsión por perfil medio (hora de la semana), sin mirar si el contador está caído."""

    def __init__(self, df):
        how = df.timestamp.dt.weekday * 24 + df.timestamp.dt.hour
        ok = df[df.load_kw > 0]
        self.prof = ok.groupby(how[ok.index])["load_kw"].mean().reindex(range(168)).ffill().bfill().to_numpy()

    def update(self, obs):
        pass

    def forecast(self, obs, h):
        idx = (obs.hour_of_week + np.arange(h)) % 168
        return self.prof[idx], np.zeros(h)


def make_agent(kind, train_df=None):
    if kind == "mpc":
        return BatteryAgent()
    if kind == "antes":
        return _Wrap(_Before())
    pol = _NoCap()
    if kind == "sin_consumo":
        pol.forecaster = _HugeLoad()
    elif kind == "persistencia":
        pol.forecaster = _Persistence()
    elif kind == "perfil":
        pol.forecaster = _ProfileOnly(train_df)
    else:
        raise ValueError(kind)
    return _Wrap(pol)


def oracle_for(df):
    b = baseline_totals(df)
    return OracleAgent(df, *score_weights(b["co2_kg"] / len(df), b["cost_eur"] / len(df)))


def run(agent, df):
    res = simulate(agent, df)
    return score(res.totals, baseline_totals(df)), res


def masked_score(log, df, mask):
    """Como evaluate_results(mask=...) del simulador oficial: solo cuentan las horas de la máscara."""
    base = np.maximum((df.load_kw - df.pv_kw).to_numpy(), 0.0)
    co2b = (base * df.co2_kg_kwh.to_numpy())[mask].sum()
    costb = (base * df.price_eur_kwh.to_numpy())[mask].sum()
    co2 = log.co2_kg.to_numpy()[mask].sum()
    cost = log.cost_eur.to_numpy()[mask].sum()
    return 70 * (1 - co2 / co2b) + 30 * (1 - cost / costb)


# ------------------------------------------------------------------------------- bloques
def bloque_calibracion(full, lines):
    env_mod_spec = importlib.util.spec_from_file_location("official_env", KIT / "environment.py")
    env_mod = importlib.util.module_from_spec(env_mod_spec)
    env_mod_spec.loader.exec_module(env_mod)
    lines += ["## 1. ¿Nuestro simulador da lo mismo que el oficial en todos los datos?", "",
              "| Datos | Horas | Score oficial | Score nuestro | Infr. oficial | Infr. nuestro |", "|---|---|---|---|---|---|"]
    ok = True
    for name, df in (("Validación", validation_split(full)), ("Train", train_split(full)), ("Todo", full)):
        off = env_mod.run_agent_simulation(BatteryAgent(), to_env_frame(df))
        ours, _ = run(BatteryAgent(), df)
        same = abs(off["score"] - round(ours["score"], 2)) < 0.011 and off["infraccions"] == ours["infractions"]
        ok &= same
        lines.append(f"| {name} | {len(df)} | {fmt(off['score'])} | {fmt(ours['score'])} | {off['infraccions']} | "
                     f"{ours['infractions']} |")
        print(f"  calibración {name:<11} oficial {off['score']:.2f}  nuestro {ours['score']:.2f}  {'OK' if same else 'DIFERENTE'}")
    lines += ["", "Coinciden." if ok else "**NO coinciden: revisar.**", ""]
    return ok


def contiguous_starts(full):
    ts = full.timestamp.to_numpy()
    ok = []
    for s in range(0, len(full) - WEEK):
        if (ts[s + WEEK - 1] - ts[s]) == np.timedelta64(WEEK - 1, "h"):
            ok.append(s)
    return np.array(ok)


def bloque_episodios(full, lines, n_ep):
    starts = contiguous_starts(full)
    rng = np.random.default_rng(2026)
    rows = []
    for ep in range(n_ep):
        chosen = []
        while len(chosen) < 12:
            s = int(rng.choice(starts))
            if all(abs(s - c) >= WEEK for c in chosen):
                chosen.append(s)
        df = pd.concat([full.iloc[s:s + WEEK] for s in sorted(chosen)], ignore_index=True)
        m, _ = run(BatteryAgent(), df)
        o, _ = run(oracle_for(df), df)
        rows.append((m["score_raw"], o["score_raw"], m["infractions"], int((df.load_kw == 0).sum())))
        print(f"  episodio {ep + 1:>2}/{n_ep}: mpc {m['score_raw']:.3f}  oracle {o['score_raw']:.3f}  "
              f"dif {o['score_raw'] - m['score_raw']:.4f}  horas a 0: {rows[-1][3]}")
    r = np.array(rows)
    gap = r[:, 1] - r[:, 0]
    clean = r[:, 3] == 0
    lines += ["## 2. Episodios tipo test: 12 semanas al azar del histórico, concatenadas", "",
              f"{n_ep} episodios de 2.016 h. Cada uno son 12 bloques de 168 h seguidas, elegidos al azar y puestos "
              "uno detrás de otro, como hace el test oficial con la última semana de cada mes.", "",
              "| | Episodios | Score medio del agente | Score medio del óptimo | Distancia media | Distancia máxima | Infracciones |",
              "|---|---|---|---|---|---|---|"]
    for name, sel in (("Sin averías del contador", clean), ("Con alguna hora de avería", ~clean), ("Todos", np.ones(len(r), bool))):
        if sel.any():
            lines.append(f"| {name} | {int(sel.sum())} | {fmt(r[sel, 0].mean())} | {fmt(r[sel, 1].mean())} | "
                         f"{fmt(gap[sel].mean(), 4)} | {fmt(gap[sel].max(), 4)} | {int(r[sel, 2].sum())} |")
    lines += ["", f"El score de un episodio va de {fmt(r[:, 0].min())} a {fmt(r[:, 0].max())} según las semanas que "
              "le toquen: la cifra del leaderboard depende sobre todo de las semanas, no del agente.", ""]
    return r


TEST_STARTS = ["2025-09-24", "2025-10-25", "2025-11-24", "2025-12-25", "2026-01-25", "2026-02-22",
               "2026-03-25", "2026-04-24", "2026-05-25", "2026-06-24", "2026-07-25", "2026-08-25"]


def test_like_episode(full, nov_zero=True, xmas=0.55, zero_week=None):
    """12 semanas con las fechas del test oficial (últimos 7 días de cada mes).

    Los datos de cada semana son los de la última semana del train de ese mes. Noviembre no tiene
    contador en el train: sus precios y su CO2 sí están, y el consumo va a 0 (nov_zero) o se copia de
    octubre. En Navidad el campus está cerrado: el consumo de esa semana se multiplica por `xmas`.
    `zero_week` pone a 0 otra semana (índice 0-11) en vez de noviembre.
    """
    val = validation_split(full)
    weeks = {str(g.timestamp.iloc[0].to_period("M")): g.reset_index(drop=True)
             for _, g in val.groupby(val.timestamp.dt.to_period("M"))}
    pr = pd.read_csv(TRAIN_DIR / "precio_pvpc.csv", parse_dates=["Fecha"]).set_index("Fecha")
    co = pd.read_csv(TRAIN_DIR / "co2_red.csv", parse_dates=["Fecha"]).set_index("Fecha")
    hours = pd.date_range("2025-11-17", periods=WEEK, freq="h")
    nov = weeks["2025-10"].copy()
    nov["price_eur_kwh"] = pr.precio_eur_per_kwh.reindex(hours).to_numpy()
    nov["co2_kg_kwh"] = co.co2_kg_per_kwh.reindex(hours).to_numpy()
    weeks["2025-11"] = nov
    out = []
    for i, start in enumerate(TEST_STARTS):
        w = weeks[start[:7]].copy()
        if start[:7] == "2025-12":
            w["load_kw"] = w.load_kw * xmas
        if (zero_week is None and nov_zero and start[:7] == "2025-11") or zero_week == i:
            w[["load_kw", "pv_kw"]] = 0.0
        w["timestamp"] = pd.date_range(start, periods=len(w), freq="h")
        out.append(w)
    return pd.concat(out, ignore_index=True)


def bloque_semana_sin_datos(full, train, lines):
    kinds = [("mpc", "Nuestro agente"), ("antes", "Nuestro agente antes"),
             ("persistencia", "LP con consumo = última hora"), ("sin_consumo", "LP que ignora el consumo")]
    lines += ["## 3. ¿Y si el test trae una semana sin datos de contador?", "",
              "En el train, noviembre no tiene datos de contador. El test son 12 semanas completas, así que la de "
              "noviembre existe y no sabemos cómo la han rellenado. Episodio con las fechas del test oficial; los datos "
              "de cada semana son los de la última semana del train de ese mes, con Navidad al 55 % de consumo.", "",
              "Todos los planteamientos usan el mismo optimizador; solo cambia cómo tratan el consumo. "
              "\"Mitad 1\" y \"mitad 2\" son el score contando solo las primeras o las últimas 1.008 horas, "
              "como hace el simulador oficial con el ranking público y el privado.", "",
              "| Escenario | Planteamiento | Completo | Mitad 1 | Mitad 2 | Vertido (kWh) |", "|---|---|---|---|---|---|"]
    out = {}
    for name, df in (("Noviembre a cero", test_like_episode(full)),
                     ("Noviembre normal", test_like_episode(full, nov_zero=False))):
        half = np.arange(len(df)) < len(df) // 2
        rows = []
        for kind, label in kinds:
            s, res = run(make_agent(kind, train), df)
            rows.append((label, s["score_raw"], masked_score(res.log, df, half), masked_score(res.log, df, ~half),
                         res.totals["export_kwh"], s["infractions"]))
        o, ores = run(oracle_for(df), df)
        rows.append(("Óptimo (conoce el futuro)", o["score_raw"], masked_score(ores.log, df, half),
                     masked_score(ores.log, df, ~half), ores.totals["export_kwh"], 0))
        for label, full_s, h1, h2, exp, infr in rows:
            assert infr == 0, (name, label)
            lines.append(f"| {name} | {label} | {fmt(full_s, 3)} | {fmt(h1, 3)} | {fmt(h2, 3)} | {exp:.0f} |")
            out[(name, label)] = (full_s, h1, h2)
            print(f"  {name:<17} {label:<30} completo {full_s:.3f}  mitad1 {h1:.3f}  mitad2 {h2:.3f}  vertido {exp:.0f}")
    gain = out[("Noviembre a cero", "Nuestro agente")][1] - out[("Noviembre a cero", "Nuestro agente antes")][1]
    lines += ["", f"Con noviembre a cero, la gestión de la semana sin datos sube el score de la primera mitad en "
              f"{fmt(gain, 3)} puntos; con noviembre normal no cambia nada. Quien ignora el consumo vierte la batería "
              "cada día de esa semana.", ""]

    # La misma prueba poniendo a cero cada una de las otras semanas: que no dependa de noviembre.
    lines += ["Poniendo a cero, de una en una, cada una de las otras semanas (score completo):", "",
              "| Semana a cero | Nuestro agente | Antes | Óptimo |", "|---|---|---|---|"]
    diffs = []
    for i in range(1, 11):
        if i == 2:
            continue
        df = test_like_episode(full, nov_zero=False, zero_week=i)
        new, _ = run(make_agent("mpc"), df)
        old, _ = run(make_agent("antes"), df)
        o, _ = run(oracle_for(df), df)
        assert new["infractions"] == 0
        diffs.append(new["score_raw"] - old["score_raw"])
        lines.append(f"| {TEST_STARTS[i][:7]} | {fmt(new['score_raw'], 3)} | {fmt(old['score_raw'], 3)} | {fmt(o['score_raw'], 3)} |")
        print(f"  semana a cero {TEST_STARTS[i][:7]}: nuevo {new['score_raw']:.4f}  antes {old['score_raw']:.4f}  oracle {o['score_raw']:.4f}")
    lines += ["", f"Diferencia con la lógica anterior: de {fmt(min(diffs), 3)} a +{fmt(max(diffs), 3)} "
              f"(media +{fmt(float(np.mean(diffs)), 3)}). Lo que queda hasta el óptimo es casi todo inevitable: "
              "el óptimo sabe de antemano que la semana viene sin datos y llega a ella con la batería vacía.", ""]
    return out


def bloque_mascara(val, lines):
    n_weeks = len(val) // WEEK
    week = np.arange(len(val)) // WEEK
    masks = {
        "Semanas alternas (pares)": week % 2 == 0,
        "Semanas alternas (impares)": week % 2 == 1,
        "Primera mitad": week < n_weeks // 2 + 1,
        "Segunda mitad": week >= n_weeks // 2 + 1,
    }
    rng = np.random.default_rng(7)
    masks["Horas al azar (50 %)"] = rng.random(len(val)) < 0.5
    mults = [0.5, 0.7, 0.85, 1.0, 1.15, 1.4, 2.0]
    table = {}
    for k in mults:
        pol = MPCPolicy()
        pol.w_cost *= k
        s, res = run(_Wrap(pol), val)
        table[k] = (s["score_raw"], {m: masked_score(res.log, val, mask) for m, mask in masks.items()})
        print(f"  peso del coste x{k:<4}: completo {s['score_raw']:.3f}  " +
              "  ".join(f"{v:.3f}" for v in table[k][1].values()))
    lines += ["## 4. El leaderboard público solo cuenta la mitad de las horas", "",
              "El mismo agente con distinto reparto entre CO₂ y coste (multiplicador del peso del coste). "
              "\"Completo\" es el score sobre todas las horas; las demás columnas son el score que se vería si solo "
              "contara esa mitad, calculado como hace el simulador oficial con su máscara.", "",
              "| Peso del coste | Completo | " + " | ".join(masks) + " |", "|---|---|" + "---|" * len(masks)]
    for k in mults:
        full_s, by = table[k]
        lines.append(f"| ×{fmt(k)} | {fmt(full_s, 3)} | " + " | ".join(fmt(v, 3) for v in by.values()) + " |")
    spread_full = max(t[0] for t in table.values()) - table[1.0][0]
    best = {m: max(table[k][1][m] for k in mults) - table[1.0][1][m] for m in masks}
    head = ("Sobre todas las horas, ningún otro reparto mejora al nuestro. " if spread_full < 5e-4 else
            f"Sobre todas las horas, otro reparto mejora al nuestro como mucho en {fmt(spread_full, 3)} puntos. ")
    lines += ["", head + "Sobre una mitad, otro reparto puede salir hasta " + fmt(max(best.values()), 3) +
              " puntos por encima sin ser mejor agente: lo que gana en esa mitad lo pierde en la otra.", ""]
    return table


def hostile_obs(rng):
    n = int(rng.choice([24, 24, 24, 24, 23, 5, 1, 0]))
    price = rng.lognormal(-2.2, 0.6, n)
    co2 = rng.lognormal(-2.5, 0.5, n)
    for arr in (price, co2):
        if n and rng.random() < 0.15:
            bad = rng.choice([np.nan, np.inf, -np.inf, 0.0, -0.05, 1e9])
            arr[rng.integers(0, n, size=max(1, n // 6))] = bad
    conv = rng.choice(["list", "tuple", "array", "series", "none"], p=[0.5, 0.1, 0.2, 0.15, 0.05])
    wrap = {"list": list, "tuple": tuple, "array": np.array, "series": pd.Series, "none": lambda a: None}[conv]
    soc = float(rng.choice([0.0, 2000.0, 1e-7, 2000 - 1e-7, rng.uniform(0, 2000), rng.uniform(0, 2000)]))
    recent = rng.choice(["ok", "zero", "nan", "none", "missing", "text", "low"], p=[0.5, 0.1, 0.1, 0.1, 0.05, 0.05, 0.1])
    nd = {"ok": {"ultim_consum_kw": float(rng.uniform(450, 2500)), "ultima_solar_kw": float(rng.uniform(0, 150))},
          "zero": {"ultim_consum_kw": 0.0, "ultima_solar_kw": 0.0},
          "nan": {"ultim_consum_kw": float("nan"), "ultima_solar_kw": float("nan")},
          "none": None, "missing": {}, "text": "sin datos",
          "low": {"ultim_consum_kw": float(rng.uniform(0, 400)), "ultima_solar_kw": float(rng.uniform(0, 500))}}[recent]
    ts = pd.Timestamp("2025-09-24") + pd.Timedelta(hours=int(rng.integers(0, 8000)))
    obs = {"timestamp": rng.choice([ts, str(ts), None]), "hour": int(ts.hour), "day_of_week": int(ts.dayofweek),
           "soc_kwh": soc, "soc_pct": soc / 2000, "soc_percent": soc / 20,
           "preu_actual": float(price[0]) if n else float(rng.lognormal(-2.2, 0.6)),
           "co2_actual": float(co2[0]) if n else float(rng.lognormal(-2.5, 0.5)),
           "preus_properes_24h": wrap(price), "co2_properes_24h": wrap(co2), "noves_dades_5min": nd}
    if rng.random() < 0.03:
        obs["soc_kwh"] = np.float32(soc)
    if rng.random() < 0.02:
        obs.pop(str(rng.choice(["timestamp", "noves_dades_5min", "soc_pct"])), None)
    return obs, soc


def bloque_fuzz(lines, n):
    rng = np.random.default_rng(123)
    agent, errors, infr, nonfinite, acted = BatteryAgent(), 0, 0, 0, 0
    for i in range(n):
        if i % 1500 == 0:
            agent = BatteryAgent()
        obs, soc = hostile_obs(rng)
        try:
            a = agent.act(obs)
        except Exception:
            errors += 1
            continue
        if not isinstance(a, float) or not math.isfinite(a):
            nonfinite += 1
            continue
        acted += abs(a) > 1e-9
        infr += apply_action(min(max(soc, 0.0), P.capacity_kwh), a)[2]
    lines += ["## 5. Fuzzing: observaciones hostiles", "",
              f"{n} observaciones con previsiones con NaN, infinitos, negativos, vacías o recortadas; listas, tuplas, "
              "arrays y Series; batería justo en los límites; lecturas del contador a cero, ausentes o en texto; "
              "campos que faltan.", "",
              "| Excepciones | Respuestas no numéricas | Infracciones | Veces que el agente actuó |", "|---|---|---|---|",
              f"| {errors} | {nonfinite} | {infr} | {int(acted)} |", ""]
    print(f"  fuzzing: {n} obs  excepciones {errors}  no finitas {nonfinite}  infracciones {infr}  actuó {int(acted)}")
    return errors + nonfinite + infr


def bloque_latencia(val, lines):
    agent = BatteryAgent()
    ts = pd.DatetimeIndex(val.timestamp)
    price, co2 = val.price_eur_kwh.to_numpy(), val.co2_kg_kwh.to_numpy()
    load_, pv = val.load_kw.to_numpy(), val.pv_kw.to_numpy()
    soc, lat = P.soc_init_kwh, []
    for t in range(len(val)):
        obs = make_official_obs(ts[t], soc, price[t:t + 24], co2[t:t + 24], load_[max(t - 1, 0)], pv[max(t - 1, 0)])
        t0 = time.perf_counter()
        a = agent.act(obs)
        lat.append(time.perf_counter() - t0)
        _, soc, _ = apply_action(soc, a)
    lat = np.array(lat) * 1000
    proj = lat.mean() * 2016 / 1000
    lines += ["## 6. Latencia por paso (en esta máquina)", "",
              "| Media | Percentil 99 | Máximo | Proyección a 2.016 pasos | Respaldos usados |", "|---|---|---|---|---|",
              f"| {fmt(lat.mean())} ms | {fmt(np.percentile(lat, 99))} ms | {fmt(lat.max())} ms | {fmt(proj, 1)} s "
              f"(límite 60 s) | {agent.policy.n_fallbacks} |", "",
              "En el servidor oficial, el dry-run midió 2,07 ms por paso.", ""]
    print(f"  latencia: media {lat.mean():.2f} ms  p99 {np.percentile(lat, 99):.2f}  máx {lat.max():.2f}  "
          f"respaldos {agent.policy.n_fallbacks}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    ensure_official()
    if is_synthetic():
        sys.exit("Hacen falta los datos oficiales: python scripts/preparar_oficial.py")
    full = load()
    val, train = validation_split(full), train_split(full)
    lines = ["# P1 · Auditoría del agente", "",
             "Generado por `python scripts/p1_auditoria.py` con los datos oficiales del train.", ""]
    print("1. calibración");            bloque_calibracion(full, lines)
    print("2. episodios tipo test");    bloque_episodios(full, lines, 6 if args.quick else 20)
    print("3. semana sin datos");       bloque_semana_sin_datos(full, train, lines)
    print("4. máscara pública");        bloque_mascara(val, lines)
    print("5. fuzzing");                bad = bloque_fuzz(lines, 3000 if args.quick else 12000)
    print("6. latencia");               bloque_latencia(val, lines)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nTablas en {OUT.relative_to(REPO)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
