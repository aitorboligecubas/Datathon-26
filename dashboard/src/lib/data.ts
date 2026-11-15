import { useQuery } from "@tanstack/react-query";

// Base relativa (funciona servido desde cualquier subruta).
const base = import.meta.env.BASE_URL;

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(`${base}data/${name}`);
  if (!res.ok) throw new Error(`No s'ha pogut carregar ${name} (${res.status})`);
  return res.json() as Promise<T>;
}

function useData<T>(name: string) {
  return useQuery<T>({ queryKey: ["data", name], queryFn: () => fetchJson<T>(name), staleTime: Infinity });
}

// ---- Tipos (coinciden con dashboard/scripts/export_data.py) ----
export interface AnnualBaseline {
  co2_t: number;
  eur: number;
  gwh: number;
  mwh_day: number;
}

export interface Kpis {
  agent_score: number;
  oracle_score: number;
  pct_of_max: number;
  agent_co2_pct: number;
  agent_cost_pct: number;
  infractions: number;
  co2_t_year_2mwh: number;
  eur_year_2mwh: number;
  annual_baseline: AnnualBaseline;
  validation_hours: number;
  validation_start: string;
  validation_end: string;
}

export interface Meta {
  generated: string;
  data_source: string;
  train_hours: number;
  train_start: string;
  train_end: string;
  weights: { co2: number; cost: number };
  battery: { capacity_kwh: number; power_kw: number; roundtrip_eff: number; soc_init_kwh: number };
}

export interface HourlyPattern {
  hour: number;
  co2_g: number;
  co2_p25: number;
  co2_p75: number;
  price_c: number;
  price_p25: number;
  price_p75: number;
  weight: number;
}
export interface Heatmap {
  months: string[];
  hours: number[];
  values: number[][];
}
export interface Patterns {
  hourly: HourlyPattern[];
  heatmap_co2: Heatmap;
  heatmap_price: Heatmap;
  conflict_hourly: { hour: number; co2_norm: number; price_norm: number }[];
  conflict_monthly: { month: string; corr: number }[];
  monthly: { month: string; co2_g: number; price_c: number }[];
  summary: {
    n_hours: number;
    co2_best_hour: number;
    co2_best_val: number;
    co2_worst_hour: number;
    co2_worst_val: number;
    co2_ratio: number;
    price_best_hour: number;
    price_best_val: number;
    price_worst_hour: number;
    price_worst_val: number;
    price_ratio: number;
    weight_best_hour: number;
    weight_worst_hour: number;
    weight_ratio: number;
    corr_hourly: number;
    overlap_clean_cheap: number;
    overlap_dirty_expensive: number;
    co2_mean_g: number;
    price_mean_c: number;
  };
}

export interface ObjectiveRow {
  label: string;
  d_co2_pct: number;
  d_cost_pct: number;
  score: number;
  is_reto: boolean;
}

export interface StrategyRow {
  name: string;
  key: string;
  score: number;
  d_co2_pct: number;
  d_cost_pct: number;
  infractions: number;
}
export interface CeilingRow {
  label: string;
  score: number;
  d_co2_pct: number;
  d_cost_pct: number;
  is_real: boolean;
}
export interface WeekPoint {
  timestamp: string;
  hour: number;
  weekday: number;
  weight: number;
  action_kw: number;
  soc_mwh: number;
  price_c: number;
  co2_g: number;
}
export interface Strategies {
  comparison: StrategyRow[];
  ceiling: CeilingRow[];
  charge_by_hour: { hour: number; charge_kwh: number; discharge_kwh: number }[];
  napkin: {
    battery_pct_daily: number;
    energy_charged_pct: number;
    energy_discharged_pct: number;
    cycles_day: number;
    weight_charge: number;
    weight_discharge: number;
    result: number;
    daily_consumption_mwh: number;
  };
  week: { start: string; end: string; points: WeekPoint[] };
}

export interface ScenarioRow {
  capacity_mwh: number;
  power_kw: number;
  score: number;
  co2_pct: number;
  cost_pct: number;
  co2_t_year: number;
  eur_year: number;
  cycles_day: number;
  marginal_co2_t: number | null;
  marginal_eur: number | null;
}
export interface Scenarios {
  proportional: ScenarioRow[];
  fixed_power: ScenarioRow[];
  annual_baseline: AnnualBaseline;
}

export interface Quality {
  night_profile: { hour: number; dataset_kw: number; real_kw: number }[];
  example: { ts: string; dataset_kw: number; real_kw: number | null; frozen: boolean }[];
  stats: {
    meter_records: number;
    com_fail_n: number;
    com_fail_pct: number;
    frozen_n: number;
    frozen_pct: number;
    night_cong_kw: number;
    night_real_kw: number;
    night_diff_pct: number;
    over_kwh_night: number;
    over_pct_daily: number;
    zero_hours: number;
    mean_load_ofi: number;
    mean_load_real: number;
    hours_ofi: number;
    hours_real: number;
  };
  variants: { variant: string; label: string; mpc: number; oracle: number; d_co2_pct: number; d_cost_pct: number }[];
}

// ---- HARD MODE (coincideix amb dashboard/scripts/export_hard.py) ----
export interface HmKpis {
  agent_score: number;
  oracle_score: number;
  pct_of_max: number;
  agent_co2_pct: number;
  agent_cost_pct: number;
  infractions: number;
  public_best: number;
  public_rank: string;
  public_record: number;
  public_teams: number;
  public_v7: number;
  public_v8: number;
  public_v6: number;
  public_v2: number;
  no_forecast_score: number;
  export_rescued_pct: number;
  surplus_hours_pct: number;
  validation_hours: number;
  validation_start: string;
  validation_end: string;
}
export interface HmMeta {
  generated: string;
  battery: { capacity_kwh: number; power_kw: number };
  solar_factor: number;
  known_hours: number;
  train_start: string;
  train_end: string;
}
export interface HmLadderRow {
  name: string;
  key: string;
  score: number;
  co2_pct: number;
  cost_pct: number;
  infr: number;
  export_kwh: number;
  export_solar: number;
  export_discharge: number;
}
export interface HmWeekPoint {
  timestamp: string;
  hour: number;
  weekday: number;
  load_kw: number;
  pv_kw: number;
  action_kw: number;
  soc_mwh: number;
  import_kw: number;
  export_kw: number;
  weight: number;
  price_c: number;
  co2_g: number;
}
export interface HmStrategies {
  ladder: HmLadderRow[];
  versions: { name: string; score: number }[];
  week: { points: HmWeekPoint[] };
}
export interface HmSolar {
  hourly: { hour: number; pv_kw: number; load_kw: number; surplus_kw: number }[];
  monthly: { month: string; pv_mwh_day: number }[];
  stats: {
    pv_factor: number;
    surplus_hours_pct: number;
    pv_peak_kw: number;
    pv_peak_hour: number;
    pv_mean_day_kw: number;
    export_base_kwh_day: number;
    export_base_kwh_year: number;
    export_v8_solar_day: number;
    export_rescued_pct: number;
    load_min_kw: number;
    load_max_kw: number;
  };
}
export interface HmForecast {
  value_ladder: { label: string; score: number; is_us?: boolean }[];
  decomposition: { label: string; points: number; color: string }[];
  net_sd: { hour: number; kw: number }[];
  market_err_pct: number;
  solar_step_kw: number;
  known_hours: number;
}

export const useHmKpis = () => useData<HmKpis>("hm_kpis.json");
export const useHmMeta = () => useData<HmMeta>("hm_meta.json");
export const useHmStrategies = () => useData<HmStrategies>("hm_strategies.json");
export const useHmSolar = () => useData<HmSolar>("hm_solar.json");
export const useHmForecast = () => useData<HmForecast>("hm_forecast.json");

// ---- OPERACIONS (monitoratge) ----
export interface OpStatus {
  timestamp: string;
  hour: number;
  weekday: number;
  soc_mwh: number;
  soc_pct: number;
  power_kw: number;
  mode: string;
  price_c: number;
  co2_g: number;
}
export interface OpToday {
  hour: number;
  action_kw: number;
  soc_mwh: number;
  import_kw: number;
  export_kw: number;
  price_c: number;
  co2_g: number;
  weight: number;
  is_now: boolean;
}
export interface OpWeek {
  co2_saved_kg: number;
  eur_saved: number;
  cycles: number;
  infractions: number;
  import_mwh: number;
  export_mwh: number;
  days: number;
  start: string;
  end: string;
}
export interface OpAlert {
  level: "good" | "warn";
  label: string;
  detail: string;
}
export interface Operations {
  battery: { capacity_mwh: number; power_kw: number };
  status: OpStatus;
  today: OpToday[];
  week: OpWeek;
  alerts: OpAlert[];
}
export const useOperations = () => useData<Operations>("operations.json");
export const useHmOperations = () => useData<Operations>("hm_operations.json");

export const useKpis = () => useData<Kpis>("kpis.json");
export const useMeta = () => useData<Meta>("meta.json");
export const usePatterns = () => useData<Patterns>("patterns.json");
export const useObjective = () => useData<{ rows: ObjectiveRow[] }>("objective.json");
export const useStrategies = () => useData<Strategies>("strategies.json");
export const useScenarios = () => useData<Scenarios>("scenarios.json");
export const useQuality = () => useData<Quality>("quality.json");
