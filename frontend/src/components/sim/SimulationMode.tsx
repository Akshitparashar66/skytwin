import { useState } from 'react'
import { CardHeader } from '../CardHeader'
import { Icon } from '../Icon'
import { api, type SimulateBody } from '../../api'
import type { AppConfig, Catalog, SimulationResult } from '../../types'
import { SERIES } from '../../lib/colors'
import { CompareView } from './CompareView'
import { ResultView } from './ResultView'
import { ScenarioBuilder, type ScenarioDraft } from './ScenarioBuilder'

export type SimOutcome = { kind: 'single'; result: SimulationResult } | { kind: 'compare'; a: SimulationResult; b: SimulationResult }

export interface SimState {
  a: ScenarioDraft
  b: ScenarioDraft
  compare: boolean
  horizon: number
  outcome: SimOutcome | null
}

export function initialSimState(catalog: Catalog): SimState {
  const preset = (id: string) => catalog.presets.find((p) => p.id === id) ?? catalog.presets[0]
  const draft = (id: string): ScenarioDraft => {
    const p = preset(id)
    return {
      label: p.label,
      perturbations: p.perturbations.map(({ kind, magnitude, start_min, duration_min }) => ({ kind, magnitude, start_min, duration_min })),
    }
  }
  return { a: draft('power_plus_20'), b: draft('power_plus_20_shed'), compare: false, horizon: 360, outcome: null }
}

const HORIZONS = [
  { value: 120, label: '2 h' },
  { value: 360, label: '6 h' },
  { value: 720, label: '12 h' },
  { value: 1440, label: '24 h' },
]

interface Props {
  catalog: Catalog | null
  config: AppConfig | null
  state: SimState | null
  setState: (s: SimState) => void
}

export function SimulationMode({ catalog, config, state, setState }: Props) {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!catalog || !state) return <div className="empty-state">Loading scenarios…</div>

  const body = (d: ScenarioDraft): SimulateBody => ({ perturbations: d.perturbations, horizon_min: state.horizon, label: d.label })

  async function run() {
    if (!state) return
    setRunning(true)
    setError(null)
    try {
      if (state.compare) {
        const { a, b } = await api.compare(body(state.a), body(state.b))
        setState({ ...state, outcome: { kind: 'compare', a, b } })
      } else {
        const result = await api.simulate(body(state.a))
        setState({ ...state, outcome: { kind: 'single', result } })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="sim-layout">
      <aside className="sim-controls">
        <section className="card run-card">
          <CardHeader title="Simulation control" icon="play" />
          <label className="field">
            <span>Prediction horizon</span>
            <div className="segmented" role="radiogroup" aria-label="Prediction horizon">
              {HORIZONS.map((h) => (
                <button
                  key={h.value}
                  role="radio"
                  aria-checked={state.horizon === h.value}
                  className={state.horizon === h.value ? 'active' : ''}
                  onClick={() => setState({ ...state, horizon: h.value })}
                >
                  {h.label}
                </button>
              ))}
            </div>
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={state.compare} onChange={(e) => setState({ ...state, compare: e.target.checked })} />
            Compare two scenarios
          </label>
          <button className="button primary" onClick={run} disabled={running}>
            <Icon name="play" size={14} />{' '}
            {running ? 'Simulating…' : state.compare ? 'Run comparison' : 'Run What-If'}
          </button>
          {error && <p className="error small">{error}</p>}
        </section>
        <ScenarioBuilder
          title={state.compare ? 'Scenario A' : 'Scenario'}
          catalog={catalog}
          value={state.a}
          onChange={(a) => setState({ ...state, a })}
          accent={SERIES[1]}
        />
        {state.compare && (
          <ScenarioBuilder
            title="Scenario B"
            catalog={catalog}
            value={state.b}
            onChange={(b) => setState({ ...state, b })}
            accent={SERIES[2]}
          />
        )}
      </aside>
      <div className={`sim-results ${running ? 'stale' : ''}`}>
        {!state.outcome && (
          <div className="empty-state">
            <h2>What would happen if…?</h2>
            <p className="muted">
              Pick a preset or build a scenario, then run it. The twin copies the current live state and propagates your change
              forward. The live spacecraft is never touched.
            </p>
          </div>
        )}
        {state.outcome?.kind === 'single' && <ResultView result={state.outcome.result} limits={config?.limits} />}
        {state.outcome?.kind === 'compare' && <CompareView a={state.outcome.a} b={state.outcome.b} limits={config?.limits} />}
      </div>
    </div>
  )
}
