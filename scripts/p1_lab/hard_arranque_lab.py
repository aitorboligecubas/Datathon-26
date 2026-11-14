"""Laboratorio del encargo "arranque" del HARD MODE. NO se empaqueta.

Owner: P1. Compara variantes en una ventana de días de cada mes, con todo lo que se aprende ajustado SIN esa
ventana (como scripts/p1_hard.py) y el agente actual en la misma ejecución.

    python scripts/p1_lab/hard_arranque_lab.py --days 8-14 --set seed        # parte 1: la semilla
    python scripts/p1_lab/hard_arranque_lab.py --days 8-14 --set perfect     # parte 2: horizonte con todo real
    python scripts/p1_lab/hard_arranque_lab.py --days 8-14 --set horizon     # parte 2: horizonte con previsiones
    python scripts/p1_lab/hard_arranque_lab.py --days 8-14 --set terminal    # parte 2: valor final
    python scripts/p1_lab/hard_arranque_lab.py --days 8-14 --set check       # comprobaciones de la semilla

No usa nunca el split val (últimas 168 h de cada mes).
"""
import argparse
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
for _extra in (str(REPO / "src"), str(REPO / "scripts"), str(REPO / "scripts" / "p1_lab")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import p1_hard as bench  # noqa: E402
import hard_arranque_cand as cand  # noqa: E402
from battery.baselines import OracleAgent  # noqa: E402
from battery.hard import HARD_PARAMS, HardPolicy  # noqa: E402
from battery.hard_market import KNOWN_HOURS, hour_index  # noqa: E402
from battery.hard_solar import HOUR_NS  # noqa: E402
from battery.optimizer import plan, score_weights  # noqa: E402
from battery.policy import greedy_action  # noqa: E402
from battery.safety import clip_action  # noqa: E402
from battery.sim import baseline_totals, score  # noqa: E402

BLOCK_GAP = pd.Timedelta(hours=6)


def prepare(days: str) -> dict:
    full = bench.hard_table()
    a, b = [int(x) for x in days.split("-")]
    d = full.timestamp.dt.day
    df = full[(d >= a) & (d <= b)].reset_index(drop=True)
    exclude = set(df.timestamp)
    fit_df = full[~full.timestamp.isin(exclude)]
    prior = bench.fit_market(exclude, fit_df)
    solar_prior = bench.fit_solar(fit_df)
    base = baseline_totals(df)
    w = score_weights(base["co2_kg"] / len(df), base["cost_eur"] / len(df))
    gap = df.timestamp.diff()
    start = (gap.isna() | (gap > BLOCK_GAP)).to_numpy()
    block = np.cumsum(start) - 1
    first = np.zeros(len(df), dtype=int)                 # horas desde el inicio del bloque
    for bl in np.unique(block):
        sel = block == bl
        first[sel] = ((df.timestamp[sel] - df.timestamp[sel].iloc[0]) / pd.Timedelta(hours=1)).astype(int)
    return {"days": days, "full": full, "df": df, "exclude": exclude, "fit_df": fit_df, "prior": prior,
            "solar_prior": solar_prior, "base": base, "w": w, "block": block, "since": first}


def run(ctx: dict, agent) -> dict:
    df, base = ctx["df"], ctx["base"]
    totals, log = bench.simulate_hard(agent, df)
    sc = score(totals, base)
    saved = np.maximum(df.load_kw - df.pv_kw, 0.0).to_numpy() - log.import_kw.to_numpy()       # kWh comprados de menos
    pts = 100.0 * saved * (0.7 * df.co2_kg_kwh.to_numpy() / base["co2_kg"] + 0.3 * df.price_eur_kwh.to_numpy() / base["cost_eur"])
    ex = log[log.export_kw > 1e-6]
    return {"score": sc["score_raw"], "infr": sc["infractions"], "pts": pts, "log": log,
            "vert_desc": float(ex[ex.action_kw < -1e-6].export_kw.sum()), "vert_solar": float(ex[ex.action_kw >= -1e-6].export_kw.sum()),
            "ms": 1000 * totals["runtime_s"] / len(df)}


def report(ctx: dict, results: dict, ref: str, months: bool = True) -> pd.DataFrame:
    df = ctx["df"]
    since, month = ctx["since"], df.timestamp.dt.strftime("%y-%m").to_numpy()
    rows = []
    r0 = results[ref]
    for name, r in results.items():
        d = r["pts"] - r0["pts"]
        row = {"variante": name, "score": r["score"], "dif": r["score"] - r0["score"], "dia1": d[since < 24].sum(),
               "dia2": d[(since >= 24) & (since < 48)].sum(), "resto": d[since >= 48].sum(), "infr": r["infr"],
               "v_desc": r["vert_desc"], "v_solar": r["vert_solar"], "ms": r["ms"]}
        if months:
            for mo in pd.unique(month):
                row[mo] = d[month == mo].sum()
        rows.append(row)
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(f"--- días {ctx['days']} ({len(df)} h) | referencia: {ref}")
    print(out.round(3).to_string(index=False))
    return out


# ----------------------------------------------------------------------------------- parte 1: semilla
def check_seed(ctx: dict) -> None:
    """La semilla no contiene horas excluidas y cada tramo usado acaba en la hora anterior a su bloque."""
    df, exclude = ctx["df"], ctx["exclude"]
    segs = cand.seed_segments(exclude)
    ex_idx = {hour_index(t) for t in exclude}
    inside = sum(1 for s in segs for j in range(len(s["load"])) if s["start"] + j in ex_idx)
    starts = df.timestamp[ctx["since"] == 0]
    ends = {s["start"] + len(s["load"]): s for s in segs}
    hit = 0
    for t0 in starts:
        s = ends.get(hour_index(t0))
        if s is not None:
            hit += 1
            assert s["start"] + len(s["load"]) - 1 < hour_index(t0)
    d = cand.hourly_readings()
    both = d.dropna(subset=["load", "table_load"])
    print(f"semilla: {len(segs)} tramos, {sum(len(s['load']) for s in segs)} lecturas | horas excluidas dentro: {inside} | "
          f"bloques del episodio: {len(starts)}, con semilla: {hit}")
    print(f"consumo del contador frente a la tabla del banco: {len(both)} horas comunes, diferencia máxima "
          f"{float((both.load - both.table_load).abs().max()):.2e} kW | horas solo con contador: "
          f"{int((d.load.notna() & d.table_load.isna()).sum())}")
    for s in segs:
        t0 = pd.Timestamp.fromordinal(s["start"] // 24) + pd.Timedelta(hours=s["start"] % 24)
        t1 = t0 + pd.Timedelta(hours=len(s["load"]) - 1)
        print(f"   {t0} -> {t1} ({len(s['load'])} h, solar {sum(v is not None for v in s['pv'])} h)"
              f"{'  <- bloque del episodio' if (s['start'] + len(s['load'])) in {hour_index(t) for t in starts} else ''}")


def shifted(segs: list, hours: int) -> list:
    """Placebo: la misma semilla, colocada `hours` horas más tarde (deja de casar con el inicio de los bloques
    salvo que hours = 0). Con hours múltiplo de 24*k y contenido de otro mes, se usa `swapped`."""
    return [{**s, "start": s["start"] + hours} for s in segs]


def swapped(segs: list, starts: list) -> list:
    """Placebo: cada bloque arranca con la semilla de OTRO mes (la del bloque siguiente), recolocada en su sitio."""
    by_end = {s["start"] + len(s["load"]): s for s in segs}
    used = [by_end[h] for h in starts if h in by_end]
    out = []
    for i, s in enumerate(used):
        other = used[(i + 1) % len(used)]
        end = s["start"] + len(s["load"])
        out.append({"start": end - len(other["load"]), "load": other["load"], "pv": other["pv"]})
    return out


def set_seed(ctx: dict) -> dict:
    p, sp, ex = ctx["prior"], ctx["solar_prior"], ctx["exclude"]
    segs = cand.seed_segments(ex)
    starts = [hour_index(t) for t in ctx["df"].timestamp[ctx["since"] == 0]]
    last = [{"start": s["start"] + len(s["load"]) - 1, "load": s["load"][-1:], "pv": s["pv"][-1:]} for s in segs]
    day = [{"start": s["start"] + max(len(s["load"]) - 25, 0), "load": s["load"][-25:], "pv": s["pv"][-25:]} for s in segs]
    nopv = [{**s, "pv": [None] * len(s["pv"])} for s in segs]
    return {
        "actual": lambda: bench.hard_agent(p, sp),
        "cand sin semilla": lambda: cand.make(p, sp, ex, seed=False),
        "CAND (semilla 48 h)": lambda: cand.make(p, sp, ex),
        "semilla 25 h": lambda: cand.make(p, sp, ex, segments=day),
        "solo la lectura anterior": lambda: cand.make(p, sp, ex, segments=last),
        "semilla sin solar": lambda: cand.make(p, sp, ex, segments=nopv),
        "placebo: otro mes": lambda: cand.make(p, sp, ex, segments=swapped(segs, starts)),
    }


# ----------------------------------------------------------------------------------- parte 2: todo real
class PerfectMPC:
    """MPC con todo real (consumo, solar, precio y CO2) en las H filas siguientes del episodio.
    Valor final: cuantil `q` del peso real del horizonte x eta_d (la receta del agente), o 0 al acabar los datos."""

    def __init__(self, df: pd.DataFrame, w: tuple, H: int = 24, q: float = 0.25, p=HARD_PARAMS):
        self.load, self.pv = df.load_kw.to_numpy(float), df.pv_kw.to_numpy(float)
        self.price, self.co2 = df.price_eur_kwh.to_numpy(float), df.co2_kg_kwh.to_numpy(float)
        self.w, self.H, self.q, self.p, self.t = w, H, q, p, 0

    def act(self, raw) -> float:
        t = self.t
        self.t += 1
        end = min(t + self.H, len(self.load))
        marginal = self.w[0] * self.co2[t:end] + self.w[1] * self.price[t:end]
        terminal = 0.0 if end - t < self.H else float(np.quantile(marginal, self.q)) * self.p.eta_discharge
        soc = float(raw["soc_kwh"])
        a = plan(soc, self.load[t:end], self.pv[t:end], self.price[t:end], self.co2[t:end], self.w[0], self.w[1], terminal, self.p)[0]
        return clip_action(a, soc, self.p)


def set_perfect(ctx: dict) -> dict:
    df, w = ctx["df"], ctx["w"]
    out = {"óptimo (todo el futuro)": lambda: OracleAgent(df, *w, p=HARD_PARAMS)}
    for H in (24, 36, 48, 72):
        out[f"todo real, H={H}, q=0.25"] = (lambda H=H: PerfectMPC(df, w, H=H))
    for q in (0.0, 0.10, 0.40, 0.50, 0.60):
        out[f"todo real, H=24, q={q:.2f}"] = (lambda q=q: PerfectMPC(df, w, H=24, q=q))
    for q in (0.10, 0.50):
        out[f"todo real, H=48, q={q:.2f}"] = (lambda q=q: PerfectMPC(df, w, H=48, q=q))
    return out


# ----------------------------------------------------------------------------------- parte 2: con previsiones
class ExpPolicy(HardPolicy):
    """HardPolicy con el valor final y la previsión de más allá de 24 h configurables (laboratorio).
    Con los valores por defecto decide exactamente como el agente actual (se comprueba en cada ejecución)."""
    term_mode = "q"          # "q": cuantil del horizonte x eta_d | "valley": reponer en el valle previsto / eta_c
    term_q = 0.25            #      | "hour": cuantil según la hora del día (tabla term_hour) | "first24": cuantil de las 24 primeras
    term_hour = None
    term_n = 4               # horas del valle
    ext_phi = None           # (precio, CO2): cuánto de la desviación prevista se mantiene 24 h después

    def extend(self, times: list, price, co2) -> tuple:
        """Más allá de 24 h el previsor de mercado da el perfil a secas. Aquí se mantiene una parte `phi` de
        la desviación prevista para la misma hora del día anterior."""
        H = len(times)
        if self.ext_phi is None or H <= 24:
            return price, co2
        v0, month = times[0].value, times[0].month
        out = []
        for name, x, phi in (("price", np.array(price, dtype=float), self.ext_phi[0]), ("co2", np.array(co2, dtype=float), self.ext_phi[1])):
            for k in range(24, H):
                if times[k].value - v0 != k * HOUR_NS or times[k].month != month:
                    continue
                b0, b1 = self.market.profile(name, times[k - 24]), self.market.profile(name, times[k])
                if b0 > 0 and b1 > 0 and x[k - 24] > 0:
                    x[k] = b1 * math.exp(phi * math.log(x[k - 24] / b0))
            out.append(x)
        return out[0], out[1]

    def terminal_for(self, marginal: np.ndarray, times: list) -> float:
        p = self.p
        if self.term_mode == "valley":
            return float(np.sort(marginal)[:self.term_n].mean()) / p.eta_charge
        if self.term_mode == "hour" and self.term_hour is not None and times[0] is not None:
            end_hour = (times[-1].hour + 1) % 24
            return float(np.quantile(marginal, self.term_hour[end_hour])) * p.eta_discharge
        if self.term_mode == "first24":
            return float(np.quantile(marginal[:24], self.term_q)) * p.eta_discharge
        return float(np.quantile(marginal, self.term_q)) * p.eta_discharge

    def plan_action(self, obs) -> float:       # copia de HardPolicy.plan_action (v8) con los dos ganchos
        self.netload.update(obs, self.weather)
        if self.no_data_block and self.no_reading:
            return clip_action(self.p.max_charge_kw, obs.soc_kwh, self.p)
        times = self.horizon_times(obs)
        if times and len(obs.price) < KNOWN_HOURS:
            times = times[:len(obs.price)]
        if not times:
            times = [None] * max(1, len(obs.price))
        H = len(times)
        if times[0] is None:
            load, pv = self.forecaster.forecast(obs, H)
        else:
            load, pv = self.netload.forecast(obs, times)
        if self.elapsed_s > self.time_budget_s:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)
        try:
            if times[0] is None:
                price, co2 = obs.price[:H], obs.co2[:H]
            else:
                price, co2 = self.market.forecast(obs, times, self.weather)
                price, co2 = self.extend(times, price, co2)
            marginal = self.w_co2 * co2 + self.w_cost * price
            ends = H < self.horizon
            terminal = 0.0 if ends else self.terminal_for(marginal, times)
            if self.no_data_block and times[0] is not None:
                try:
                    load, pv, terminal = self.no_data_week(times, load, pv, terminal, ends)
                except Exception:
                    pass
            actions = plan(obs.soc_kwh, load, pv, price, co2, self.w_co2, self.w_cost, terminal, self.p)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)


def exp_agent(ctx: dict, seed: bool = False, **attrs):
    agent = cand.make(ctx["prior"], ctx["solar_prior"], ctx["exclude"], seed=seed)
    agent.policy.__class__ = ExpPolicy
    for k, v in attrs.items():
        setattr(agent.policy, k, v)
    return agent


def fit_phi(ctx: dict) -> tuple:
    """Cuánto de la desviación frente al perfil se mantiene 24 h después (pendiente por mínimos cuadrados),
    con el train sin la ventana y dentro del mismo mes."""
    m = bench.market_frame()
    m = m[~m.index.isin(ctx["exclude"])]
    typ = bench.market_types(m.index)
    out = []
    for name in ("price", "co2"):
        prof = np.asarray(ctx["prior"][name])[m.index.month - 1, typ, m.index.hour]
        z = pd.Series(np.log(np.clip(m[name].to_numpy(), 1e-6, None) / np.clip(prof, 1e-6, None)), index=m.index)
        z = z.reindex(pd.date_range(m.index.min(), m.index.max(), freq="h"))
        y = z.shift(-24)
        ok = z.notna() & y.notna() & ((z.index + pd.Timedelta(hours=24)).month == z.index.month)
        out.append(float((z[ok] * y[ok]).sum() / (z[ok] ** 2).sum()))
    return tuple(out)


def fit_term_hour(ctx: dict) -> list:
    """Valor final por hora del día, aprendido del óptimo en el train (sin la ventana): el precio sombra de
    la energía guardada (dual de la dinámica del LP con todo el futuro) se expresa como cuantil del peso de las
    24 h anteriores a esa hora, y se toma la mediana por hora del día."""
    import scipy.sparse as sp
    from scipy.optimize import linprog
    fit, p, w = ctx["fit_df"], HARD_PARAMS, score_weights(ctx["prior"]["co2_ref_kg_per_h"], ctx["prior"]["cost_ref_eur_per_h"])
    n = len(fit)
    net = (fit.load_kw - fit.pv_kw).to_numpy(float)
    weight = w[0] * fit.co2_kg_kwh.to_numpy(float) + w[1] * fit.price_eur_kwh.to_numpy(float)
    eye, zero = sp.identity(n, format="csr"), sp.csr_matrix((n, n))
    shift = sp.diags([np.ones(n - 1)], [-1], shape=(n, n), format="csr")
    A = sp.vstack([sp.hstack([-eye, eye, eye, -eye, zero]),
                   sp.hstack([-p.eta_charge * eye, (1.0 / p.eta_discharge) * eye, zero, zero, eye - shift])], format="csr")
    b_dyn = np.zeros(n)
    b_dyn[0] = p.soc_init_kwh
    c = np.concatenate([np.zeros(2 * n), weight, np.zeros(2 * n)])
    bounds = [(0.0, p.max_charge_kw)] * n + [(0.0, p.max_discharge_kw)] * n + [(0.0, None)] * (2 * n) + [(0.0, p.capacity_kwh)] * n
    res = linprog(c, A_eq=A, b_eq=np.concatenate([net, b_dyn]), bounds=bounds, method="highs")
    lam = -np.asarray(res.eqlin.marginals[n:])        # valor de 1 kWh guardado al EMPEZAR la hora k (>= 0)
    hour = fit.timestamp.dt.hour.to_numpy()
    q = np.full(n, np.nan)
    for k in range(24, n):
        win = weight[k - 24:k] * p.eta_discharge
        q[k] = float((win < lam[k]).mean())
    table = [float(np.nanmedian(q[hour == h])) for h in range(24)]
    return [min(max(v, 0.0), 1.0) for v in table]


def set_horizon(ctx: dict) -> dict:
    phi = fit_phi(ctx)
    print(f"persistencia de la desviación a 24 h (precio, CO2): {phi[0]:.3f}, {phi[1]:.3f}")
    out = {"actual": lambda: bench.hard_agent(ctx["prior"], ctx["solar_prior"]),
           "exp H=24 (debe ser = actual)": lambda: exp_agent(ctx)}
    for H in (30, 36, 48):
        out[f"H={H}, perfil a secas"] = (lambda H=H: exp_agent(ctx, horizon=H))
        out[f"H={H}, nivel x phi"] = (lambda H=H: exp_agent(ctx, horizon=H, ext_phi=phi))
    out["H=48, nivel x phi, valor final con 24 h"] = lambda: exp_agent(ctx, horizon=48, ext_phi=phi, term_mode="first24")
    out["H=18"] = lambda: exp_agent(ctx, horizon=18)
    return out


def set_terminal(ctx: dict) -> dict:
    table = fit_term_hour(ctx)
    print("cuantil del valor final por hora del día (del óptimo en el train):", " ".join(f"{v:.2f}" for v in table))
    out = {"actual": lambda: bench.hard_agent(ctx["prior"], ctx["solar_prior"])}
    for q in (0.0, 0.10, 0.20, 0.30, 0.40, 0.50):
        out[f"cuantil {q:.2f}"] = (lambda q=q: exp_agent(ctx, term_q=q))
    out["valle previsto (4 h) / eta_c"] = lambda: exp_agent(ctx, term_mode="valley")
    out["valle previsto (6 h) / eta_c"] = lambda: exp_agent(ctx, term_mode="valley", term_n=6)
    out["por hora del día (del óptimo)"] = lambda: exp_agent(ctx, term_mode="hour", term_hour=table)
    return out


SETS = {"seed": set_seed, "perfect": set_perfect, "horizon": set_horizon, "terminal": set_terminal}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", default="8-14")
    ap.add_argument("--set", default="seed", help="seed, perfect, horizon, terminal o check")
    ap.add_argument("--only", default="", help="trozos de nombre de las variantes a ejecutar, separados por comas")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if args.days.strip() == "val":
        raise SystemExit("la ventana val está reservada al verificador")
    t0 = time.perf_counter()
    ctx = prepare(args.days)
    print(f"[{args.days}] preparado en {time.perf_counter() - t0:.1f} s")
    if args.set == "check":
        check_seed(ctx)
        return 0
    variants = SETS[args.set](ctx)
    keep = [s for s in args.only.split(",") if s]
    results = {}
    for i, (name, fac) in enumerate(variants.items()):
        if keep and i > 0 and not any(s in name for s in keep):
            continue
        results[name] = run(ctx, fac())
    ref = next(iter(results))
    out = report(ctx, results, ref)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.out, index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
