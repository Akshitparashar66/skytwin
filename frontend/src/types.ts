export type Severity = 'warning' | 'critical'
export type Status = 'NOMINAL' | 'WARNING' | 'CRITICAL'
export type RiskLevel = 'NOMINAL' | 'CAUTION' | 'WARNING' | 'CRITICAL'

export interface Frame {
  t_s: number
  t_min: number
  orbit_number: number
  orbit_phase: number
  in_eclipse: boolean
  solar_power_w: number
  load_power_w: number
  power_margin_w: number
  battery_current_a: number
  battery_voltage_v: number
  soc_pct: number
  battery_temp_c: number
  bus_temp_c: number
  heater_on: boolean
  data_buffer_mb: number
  data_buffer_pct: number
  link_up: boolean
  payload_on: boolean
  mode: 'NOMINAL' | 'SAFE'
  safe_mode_reason: string | null
}

export interface HistoryFrame extends Frame {
  status: Status
  anomaly_count: number
}

export interface Anomaly {
  channel: string
  label: string
  unit: string
  measured: number
  expected: number
  residual: number
  score: number
  threshold: number
}

export interface LimitViolation {
  channel: string
  label: string
  unit: string
  severity: Severity
  bound: 'low' | 'high'
  limit: number
  value: number
}

export interface Alert {
  id: number
  t_min: number
  kind: 'anomaly' | 'limit' | 'mode'
  channel: string
  severity: Severity
  message: string
}

export interface PerturbationOut {
  kind: string
  magnitude: number | null
  start_min: number
  duration_min: number | null
  label: string
}

export interface Fault extends PerturbationOut {
  injected_at_min: number
}

export interface TelemetryMessage {
  type: 'telemetry'
  frame: Frame
  expected: Record<string, number>
  anomalies: Anomaly[]
  limit_violations: LimitViolation[]
  status: Status
  faults: Fault[]
  new_alerts: Alert[]
}

export interface HistoryMessage {
  type: 'history'
  frames: HistoryFrame[]
  alerts: Alert[]
}

export interface Limit {
  channel: string
  label: string
  unit: string
  warn_low: number | null
  crit_low: number | null
  warn_high: number | null
  crit_high: number | null
}

export interface AppConfig {
  limits: Limit[]
  orbit_period_min: number
  tick_sim_s: number
  tick_interval_s: number
  battery_capacity_wh: number
  solar_array_peak_w: number
}

export interface KindSpec {
  kind: string
  label: string
  description: string
  category: 'fault' | 'operation' | 'mitigation'
  impulse: boolean
  default_duration_min: number | null
  requires_duration: boolean
  magnitude: { label: string; unit: string; default: number; min: number; max: number } | null
}

export interface Preset {
  id: string
  label: string
  description: string
  perturbations: PerturbationOut[]
}

export interface Catalog {
  kinds: KindSpec[]
  presets: Preset[]
}

export interface PerturbationIn {
  kind: string
  magnitude?: number | null
  start_min?: number
  duration_min?: number | null
}

export interface SimPoint {
  t_min: number
  soc_pct: number
  battery_voltage_v: number
  battery_current_a: number
  battery_temp_c: number
  bus_temp_c: number
  solar_power_w: number
  load_power_w: number
  power_margin_w: number
  data_buffer_mb: number
  data_buffer_pct: number
  in_eclipse: boolean
  payload_on: boolean
  link_up: boolean
  heater_on: boolean
  mode: 'NOMINAL' | 'SAFE'
  safe_mode_reason: string | null
}

export type BandRow = { t_min: number } & Record<string, number>

export interface Impact {
  key: string
  label: string
  unit: string
  baseline: number | null
  predicted: number | null
  delta: number | null
  direction: 'up' | 'down' | 'flat'
  effect: 'worse' | 'better' | 'neutral'
}

export interface Finding {
  channel: string
  label: string
  unit: string
  bound: 'low' | 'high' | 'state'
  severity: Severity
  limit: number | null
  first_crossing_min: number
  extreme: number | null
  confidence: 'likely' | 'possible'
  pre_existing: boolean
  reason?: string | null
}

export interface SimSummary {
  endurance_h: number | null
  endurance_basis: string
  baseline_endurance_h: number | null
  recovery_applicable: boolean
  recovery_min: number | null
  safe_mode_at_min: number | null
  safe_mode_reason: string | null
}

export interface SimulationResult {
  label: string
  perturbations: PerturbationOut[]
  horizon_min: number
  start_t_min: number
  baseline: SimPoint[]
  scenario: SimPoint[]
  band: BandRow[]
  impacts: Impact[]
  findings: Finding[]
  risk_level: RiskLevel
  summary: SimSummary
  narrative: string[]
  recommendations: string[]
}

export interface ValidationMetrics {
  channels: number
  labelled_anomalies: number
  true_positives: number
  false_positives: number
  false_negatives: number
  precision: number
  recall: number
  f1: number
}

export interface ValidationMethod {
  id: 'statistical' | 'lstm' | string
  name: string
  description: string
  variant: string
  config: Record<string, number | boolean>
  smap_tuning: ValidationMetrics
  msl_held_out: ValidationMetrics
  model?: { window: number; horizon?: number; hidden: number; layers: number; epochs_run: number; best_val_mse: number; created_at: string; device: string }
}

export type ValidationReport =
  | { available: false }
  | {
      available: true
      generated_at: string
      dataset: string
      protocol: string
      detector: string
      reference: string
      methods: ValidationMethod[]
    }
