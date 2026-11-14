"""Candidatos de la rama `mejora-score-hard` para scripts/p1_lab/mejora_grid.py. NO se empaqueta."""
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from battery import hard_solar as hs  # noqa: E402
from p1_hard import hard_agent  # noqa: E402


class SolarCandZ(hs.SolarCand):
    """SolarCand con márgenes separados: z_dis (tope de la descarga de esta hora), z_chg (excedente que se carga
    seguro) y z_plan (lo que el plan de las horas siguientes descuenta del consumo neto)."""

    def __init__(self, prior, base, z_dis=1.4, z_chg=1.4, z_plan=1.4, z_now_plan=None, **kw):
        super().__init__(prior, base, z=z_plan, **kw)
        self.z_dis, self.z_chg, self.z_plan = z_dis, z_chg, z_plan
        self.z_now_plan = z_dis if z_now_plan is None else z_now_plan

    def forecast_tables(self, times):
        H = len(times)
        now = times[0]
        v0 = now.value
        hist = self.r_hist
        n = len(hist)
        r1 = hist[-1] if n >= 1 else float("nan")
        ry1 = hist[-25] if n >= 25 else float("nan")
        have_r1 = math.isfinite(r1)
        frozen = self.load_prev if (self.freeze and now.hour in hs.FROZEN_HOURS) else float("nan")
        in_night = math.isfinite(frozen)
        day0 = now.day
        day_mean = self.day_sum / self.day_n if self.day_n > 0 else float("nan")
        load, pv, margin = np.empty(H), np.empty(H), np.empty(H)
        pv_margin0 = 0.0
        for k, t in enumerate(times):
            h = t.hour
            seguido = t.value - v0 == k * hs.HOUR_NS
            prof = self.profile(t)
            if not math.isfinite(prof):
                prof = self.load_prev if math.isfinite(self.load_prev) else 0.0
            lo_rel = self.l_lo[h]
            if in_night and seguido and h in hs.FROZEN_HOURS:
                load_k = frozen
            else:
                in_night = False
                dev = 0.0
                if seguido and k < 24 and have_r1:
                    ry = hist[k - 24] if n >= 24 - k else float("nan")
                    if math.isfinite(ry) and math.isfinite(ry1):
                        c = self.reg3[h][k]
                        dev = c[0] * r1 + c[1] * ry + c[2] * ry1 + c[3]
                    else:
                        c = self.reg1[h][k]
                        dev = c[0] * r1 + c[1]
                elif k == 0:
                    lo_rel = self.l_lo0[h]
                load_k = prof * (1.0 + dev)
            clear, mean = self.sky_at(t)
            kappa = 0.0
            if clear > 0:
                dev = 0.0
                if seguido:
                    if t.day == day0:
                        if self.day_n > 0:
                            if k < hs.PV_LEADS:
                                dev = self.pv_a[k] * self.last_dev + self.pv_b[k] * day_mean
                        elif math.isfinite(self.prev_day_mean):
                            dev = self.pv_c * self.prev_day_mean
                    elif self.day_n >= hs.MIN_DAY_HOURS:
                        dev = self.pv_c * day_mean
                    elif self.day_n == 0 and math.isfinite(self.prev_day_mean):
                        dev = self.pv_c * self.pv_c * self.prev_day_mean
                kappa = min(max(mean / clear + dev, 0.0), hs.KAPPA_MAX)
                pv_k = clear * kappa
            else:
                pv_k = max(mean, 0.0)
            b = 0
            while b < len(hs.KAPPA_BINS) and kappa >= hs.KAPPA_BINS[b]:
                b += 1
            up = self.pv_up[b]
            m_load, m_pv = lo_rel * prof, up * clear
            margin[k] = math.sqrt(m_load * m_load + m_pv * m_pv)
            if k == 0:
                pv_margin0 = m_pv
            load[k], pv[k] = load_k, pv_k
        if self.meter_down:
            load[0] = 0.0
            if self.pv_alive:
                margin[0] = pv_margin0
            else:
                pv[0], margin[0] = 0.0, 0.0
        load, pv = np.maximum(load, 0.0), np.maximum(pv, 0.0)
        self.net_lo0 = float(load[0] - pv[0]) - self.z_dis * float(margin[0])
        self.net_lo0_charge = float(load[0] - pv[0]) - self.z_chg * float(margin[0])
        self.fresh = True
        self.last_margin, self.last_pv = margin.copy(), pv.copy()
        shade = self.z_plan * margin
        shade[0] = self.z_now_plan * float(margin[0])
        return load, pv + shade


def solar_z(**z):
    def factory(prior, solar_prior, exclude):
        a = hard_agent(prior, solar_prior)
        a.policy.netload = SolarCandZ(solar_prior["cand"], a.policy.forecaster, **z)
        return a
    return factory


def base(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior)


CANDS = {
    "base": base,
    "z14_copia": solar_z(z_dis=1.4, z_chg=1.4, z_plan=1.4),
    "dis1.0": solar_z(z_dis=1.0, z_chg=1.4, z_plan=1.4),
    "dis1.8": solar_z(z_dis=1.8, z_chg=1.4, z_plan=1.4),
    "chg0.5": solar_z(z_dis=1.4, z_chg=0.5, z_plan=1.4),
    "chg2.0": solar_z(z_dis=1.4, z_chg=2.0, z_plan=1.4),
    "plan0.7": solar_z(z_dis=1.4, z_chg=1.4, z_plan=0.7),
    "plan2.0": solar_z(z_dis=1.4, z_chg=1.4, z_plan=2.0),
    "plan0": solar_z(z_dis=1.4, z_chg=1.4, z_plan=0.0),
}



def no_seed(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, use_seed=False)


from battery import hard as hd  # noqa: E402
from battery.optimizer import plan as lp_plan  # noqa: E402
from battery.safety import clip_action  # noqa: E402
from battery.policy import greedy_action  # noqa: E402


class HardPolicyCap(hd.HardPolicy):
    """El plan usa la solar esperada (sin inflar) y limita la descarga de cada hora a
    consumo neto previsto - z_cap * margen. `z_cap_now` para la hora actual."""
    z_cap = 1.4
    z_cap_now = 1.4

    def plan_action(self, obs):
        self.netload.update(obs, self.weather)
        if self.no_data_block and self.no_reading:
            return clip_action(self.p.max_charge_kw, obs.soc_kwh, self.p)
        times = self.horizon_times(obs)
        if times and len(obs.price) < hd.KNOWN_HOURS:
            times = times[:len(obs.price)]
        if not times:
            times = [None] * max(1, len(obs.price))
        H = len(times)
        cap = None
        if times[0] is None:
            load, pv = self.forecaster.forecast(obs, H)
        else:
            load, pv = self.netload.forecast(obs, times)
            m = getattr(self.netload, "last_margin", None)
            if m is not None and len(m) == H:
                pv = self.netload.last_pv
                zz = np.full(H, self.z_cap); zz[0] = self.z_cap_now
                cap = np.maximum(load - pv - zz * m, 0.0)
        try:
            if times[0] is None:
                price, co2 = obs.price[:H], obs.co2[:H]
            else:
                price, co2 = self.market.forecast(obs, times, self.weather)
            marginal = self.w_co2 * co2 + self.w_cost * price
            ends = H < self.horizon
            terminal = 0.0 if ends else float(np.quantile(marginal, self.terminal_quantile)) * self.p.eta_discharge
            if self.no_data_block and times[0] is not None:
                try:
                    load, pv, terminal = self.no_data_week(times, load, pv, terminal, ends)
                    cap = None
                except Exception:
                    pass
            actions = lp_plan(obs.soc_kwh, load, pv, price, co2, self.w_co2, self.w_cost, terminal, self.p,
                              discharge_cap=cap)
            return clip_action(actions[0], obs.soc_kwh, self.p)
        except Exception:
            self.n_fallbacks += 1
            return greedy_action(obs, load[0], pv[0], self.p)


def capped(z_cap=1.4, z_cap_now=1.4, z_dis=1.4, z_chg=1.4):
    def factory(prior, solar_prior, exclude):
        a = hard_agent(prior, solar_prior)
        a.policy.netload = SolarCandZ(solar_prior["cand"], a.policy.forecaster, z_dis=z_dis, z_chg=z_chg, z_plan=0.0,
                                      z_now_plan=0.0)
        a.policy.__class__ = HardPolicyCap
        a.policy.z_cap, a.policy.z_cap_now = z_cap, z_cap_now
        return a
    return factory


CANDS = {
    "base": base,
    "cap1.4": capped(1.4),
    "cap1.0": capped(1.0),
    "cap1.8": capped(1.8),
    "cap2.4": capped(2.4),
}


class MarketScale:
    """Envuelve el previsor de mercado: para las horas no conocidas, x = perfil * (x_previsto / perfil) ** alpha."""

    def __init__(self, inner, alpha):
        self.inner, self.alpha = inner, alpha

    def forecast(self, obs, times, weather=None):
        p, c = self.inner.forecast(obs, times, weather)
        n = min(len(obs.price), len(obs.co2))
        out = []
        for name, x in (("price", p), ("co2", c)):
            x = np.array(x, dtype=float)
            for k in range(n, len(times)):
                if times[k] is None:
                    continue
                b = self.inner.profile(name, times[k])
                if b > 0 and x[k] > 0 and math.isfinite(b):
                    x[k] = b * (x[k] / b) ** self.alpha
            out.append(x)
        return out[0], out[1]


def mkt(alpha, **z):
    def factory(prior, solar_prior, exclude):
        a = solar_z(**z)(prior, solar_prior, exclude) if z else hard_agent(prior, solar_prior)
        a.policy.market = MarketScale(a.policy.market, alpha)
        return a
    return factory


CANDS = {
    "base": base,
    "plan2.0": solar_z(z_dis=1.4, z_chg=1.4, z_plan=2.0),
    "plan2.5": solar_z(z_dis=1.4, z_chg=1.4, z_plan=2.5),
    "plan3.0": solar_z(z_dis=1.4, z_chg=1.4, z_plan=3.0),
    "mkt0.8": mkt(0.8),
    "mkt1.2": mkt(1.2),
    "mkt1.5": mkt(1.5),
}


def v8(prior, solar_prior, exclude):
    a = hard_agent(prior, solar_prior, use_seed=False)
    a.policy.netload.z_plan = 1.4
    return a


def v9(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior)


def v9_bad_seed(prior, solar_prior, exclude):
    bad = dict(solar_prior)
    bad["seed"] = [{**s, "load": [v * 1.3 for v in s["load"]]} for s in solar_prior["seed"]]
    a = hard_agent(prior, bad)
    return a


def v9_no_seed(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, use_seed=False)


CANDS = {"base": v8, "v9": v9, "v9_semilla_mala": v9_bad_seed, "v9_sin_semilla": v9_no_seed}


def v9_safe(prior, solar_prior, exclude):
    return hard_agent(prior, solar_prior, seed_first_hour=False)


def v9_safe_bad_seed(prior, solar_prior, exclude):
    bad = dict(solar_prior)
    bad["seed"] = [{**s, "load": [v * 1.3 for v in s["load"]]} for s in solar_prior["seed"]]
    return hard_agent(prior, bad, seed_first_hour=False)


CANDS = {"base": v8, "v9": v9, "v9_semilla_mala": v9_bad_seed, "v9_sin_semilla": v9_no_seed,
         "v9_segura": v9_safe, "v9_segura_semilla_mala": v9_safe_bad_seed}


def seed_only(prior, solar_prior, exclude):
    a = hard_agent(prior, solar_prior)
    a.policy.netload.z_plan = 1.4
    return a


def zp(zp_):
    def f(prior, solar_prior, exclude):
        a = hard_agent(prior, solar_prior)
        a.policy.netload.z_plan = zp_
        return a
    return f


CANDS = {"base": v8, "semilla+plan2.0 (v9)": v9, "semilla (plan 1.4)": seed_only, "semilla+plan1.7": zp(1.7)}
