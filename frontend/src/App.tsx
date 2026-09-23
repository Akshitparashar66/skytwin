import { useEffect, useState } from 'react'
import { api } from './api'
import { useLiveTelemetry } from './hooks/useLiveTelemetry'
import type { AppConfig, Catalog, ValidationReport } from './types'
import { missionTime } from './lib/format'
import { Icon } from './components/Icon'
import { LiveMode } from './components/live/LiveMode'
import { SimulationMode, initialSimState, type SimState } from './components/sim/SimulationMode'

type Mode = 'live' | 'sim'

const HEADERS: Record<Mode, { title: string; subtitle: string; tag: string }> = {
  live: { title: 'Live telemetry', subtitle: 'Tracking the spacecraft through its digital twin', tag: 'Telemetry stream' },
  sim: {
    title: 'What-If simulation',
    subtitle: 'Predictions run on a copy of the twin. Nothing is sent to the spacecraft.',
    tag: 'Sandbox',
  },
}

export default function App() {
  const [mode, setMode] = useState<Mode>('live')
  const live = useLiveTelemetry()
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [validation, setValidation] = useState<ValidationReport | null>(null)
  const [simState, setSimState] = useState<SimState | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.config(), api.scenarios(), api.validation()])
      .then(([cfg, cat, val]) => {
        setConfig(cfg)
        setCatalog(cat)
        setValidation(val)
        setSimState((s) => s ?? initialSimState(cat))
        setLoadError(null)
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
  }, [live.connection === 'open'])

  const frame = live.latest?.frame
  const header = HEADERS[mode]
  const linkLabel = live.connection === 'open' ? 'connected' : live.connection === 'connecting' ? 'connecting…' : 'reconnecting…'

  return (
    <div className={`app mode-${mode}`}>
      <nav className="rail" aria-label="Mode">
        <div className="rail-inner">
          <div className="rail-brand">
            <span className="rail-mark">
              <Icon name="satellite" size={22} />
            </span>
            <span className="rail-name">SkyTwin</span>
          </div>
          <div className="rail-items" role="tablist">
            <button role="tab" aria-selected={mode === 'live'} className="rail-item rail-live" onClick={() => setMode('live')}>
              <Icon name="live" size={20} />
              <span>Live</span>
            </button>
            <button role="tab" aria-selected={mode === 'sim'} className="rail-item rail-sim" onClick={() => setMode('sim')}>
              <Icon name="sim" size={20} />
              <span>Simulation</span>
            </button>
          </div>
          <span className={`rail-conn conn-${live.connection}`} title={`Telemetry link: ${linkLabel}`} />
        </div>
      </nav>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">
            <div className="title-row">
              <h1>{header.title}</h1>
              <span className="mode-tag">{header.tag}</span>
            </div>
            <p className="muted">{header.subtitle}</p>
          </div>
          <div className="topbar-status">
            <span className={`link-pill conn-${live.connection}`}>
              <span className="dot" aria-hidden /> Telemetry link: {linkLabel}
            </span>
            <div className="clock">
              <span className="clock-label">Mission clock</span>
              <span className="clock-time">{frame ? missionTime(frame.t_min) : 'T+--:--'}</span>
            </div>
            {frame && (
              <span className="orbit-chip">
                <Icon name={frame.in_eclipse ? 'moon' : 'sun'} size={16} />
                Orbit {frame.orbit_number} · {frame.in_eclipse ? 'Eclipse' : 'Sunlit'}
              </span>
            )}
          </div>
        </header>
        {mode === 'sim' && (
          <div className="sandbox-strip">
            <Icon name="shield" size={14} /> Simulation sandbox · runs on a copy of the live state · no commands leave this screen
          </div>
        )}
        {loadError && <div className="banner-error">Backend unreachable: {loadError}. Is the API running on :8000?</div>}
        <main className="content">
          {mode === 'live' ? (
            <LiveMode live={live} config={config} catalog={catalog} validation={validation} />
          ) : (
            <SimulationMode catalog={catalog} config={config} state={simState} setState={setSimState} />
          )}
        </main>
      </div>
    </div>
  )
}
