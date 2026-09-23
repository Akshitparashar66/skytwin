import type {
  Alert,
  AppConfig,
  Catalog,
  Fault,
  PerturbationIn,
  SimulationResult,
  ValidationReport,
} from './types'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status)
  }
  return res.json() as Promise<T>
}

export interface SimulateBody {
  perturbations: PerturbationIn[]
  horizon_min: number
  label?: string
}

export const api = {
  config: () => request<AppConfig>('/api/config'),
  scenarios: () => request<Catalog>('/api/scenarios'),
  validation: () => request<ValidationReport>('/api/validation'),
  alerts: () => request<Alert[]>('/api/live/alerts'),
  faults: () => request<Fault[]>('/api/live/faults'),
  injectFault: (p: PerturbationIn) => request<Fault[]>('/api/live/faults', { method: 'POST', body: JSON.stringify(p) }),
  clearFaults: () => request<Fault[]>('/api/live/faults', { method: 'DELETE' }),
  simulate: (body: SimulateBody) =>
    request<SimulationResult>('/api/simulate', { method: 'POST', body: JSON.stringify(body) }),
  compare: (a: SimulateBody, b: SimulateBody) =>
    request<{ a: SimulationResult; b: SimulationResult }>('/api/compare', {
      method: 'POST',
      body: JSON.stringify({ a, b }),
    }),
}

export function telemetrySocketUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/telemetry`
}
