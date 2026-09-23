import { useMemo } from 'react'
import type { LiveTelemetry } from '../../hooks/useLiveTelemetry'
import type { AppConfig, Catalog, HistoryFrame, ValidationReport } from '../../types'
import { missionTime, num } from '../../lib/format'
import { CHROME, SERIES } from '../../lib/colors'
import { limitLines, ranges } from '../../lib/series'
import { ChartCard } from '../ChartCard'
import { StatusBadge } from '../StatusBadge'
import { TimeChart } from '../TimeChart'
import { AlertsPanel } from './AlertsPanel'
import { FaultPanel } from './FaultPanel'
import { ResidualPanel } from './ResidualPanel'
import { StatTiles } from './StatTiles'
import { ValidationCard } from './ValidationCard'

interface Props {
  live: LiveTelemetry
  config: AppConfig | null
  catalog: Catalog | null
  validation: ValidationReport | null
}

const WINDOW_FRAMES = 380

function sampleTable(frames: HistoryFrame[], cols: { label: string; get: (f: HistoryFrame) => string }[]) {
  const step = Math.max(1, Math.ceil(frames.length / 24))
  const rows = frames.filter((_, i) => i % step === 0).map((f) => [missionTime(f.t_min), ...cols.map((c) => c.get(f))])
  return { columns: ['Time', ...cols.map((c) => c.label)], rows }
}

export function LiveMode({ live, config, catalog, validation }: Props) {
  const { latest, frames, alerts } = live
  const windowFrames = useMemo(() => frames.slice(-WINDOW_FRAMES), [frames])
  const eclipses = useMemo(() => ranges(windowFrames, (f) => f.t_min, (f) => f.in_eclipse), [windowFrames])
  const xDomain: [number, number] | undefined = windowFrames.length
    ? [windowFrames[0].t_min, windowFrames[windowFrames.length - 1].t_min]
    : undefined

  if (!latest) {
    return <div className="empty-state">Waiting for telemetry…</div>
  }

  const f = latest.frame
  return (
    <div className="live-layout">
      <div className="status-strip card">
        <StatusBadge level={latest.status} size="lg" />
        <div className="status-text">
          {latest.status === 'NOMINAL' && 'All subsystems nominal. Telemetry matches the twin.'}
          {latest.status !== 'NOMINAL' &&
            [
              ...latest.anomalies.map((a) => `${a.label} deviates from the twin`),
              ...latest.limit_violations.map((v) => `${v.label} beyond ${v.severity} limit`),
              ...(f.mode === 'SAFE' ? [`SAFE mode: ${f.safe_mode_reason}`] : []),
            ].join(' · ')}
        </div>
        <div className="orbit-info muted small">
          Orbit {f.orbit_number} · {num(f.orbit_phase * 100, 0)}% · {f.in_eclipse ? 'Eclipse' : 'Sunlit'}
        </div>
      </div>

      <StatTiles frame={f} violations={latest.limit_violations} capacityWh={config?.battery_capacity_wh ?? 150} />

      <div className="live-grid">
        <div className="chart-column">
          <ChartCard
            title="Power"
            subtitle="Solar generation vs spacecraft load · shaded = eclipse"
            legend={[
              { label: 'Solar array', color: SERIES[1] },
              { label: 'Load', color: SERIES[2] },
              { label: 'Eclipse', color: CHROME.eclipse, kind: 'band' },
            ]}
            table={sampleTable(windowFrames, [
              { label: 'Solar (W)', get: (x) => num(x.solar_power_w) },
              { label: 'Load (W)', get: (x) => num(x.load_power_w) },
            ])}
          >
            <TimeChart
              data={windowFrames}
              series={[
                { key: 'solar_power_w', label: 'Solar array', color: SERIES[1] },
                { key: 'load_power_w', label: 'Load', color: SERIES[2] },
              ]}
              shade={eclipses}
              unit="W"
              xFormatter={missionTime}
              xDomain={xDomain}
              yDomain={[0, 'auto']}
            />
          </ChartCard>
          <ChartCard
            title="Battery state of charge"
            subtitle="Dashed lines are warning / critical limits"
            table={sampleTable(windowFrames, [{ label: 'SOC (%)', get: (x) => num(x.soc_pct) }])}
          >
            <TimeChart
              data={windowFrames}
              series={[{ key: 'soc_pct', label: 'SOC', color: SERIES[1] }]}
              limits={limitLines(config?.limits, 'soc_pct')}
              shade={eclipses}
              unit="%"
              xFormatter={missionTime}
              xDomain={xDomain}
              yDomain={[0, 100]}
            />
          </ChartCard>
          <ChartCard
            title="Temperatures"
            subtitle="Dashed lines are the battery limits"
            legend={[
              { label: 'Bus', color: SERIES[1] },
              { label: 'Battery', color: SERIES[2] },
            ]}
            table={sampleTable(windowFrames, [
              { label: 'Bus (°C)', get: (x) => num(x.bus_temp_c) },
              { label: 'Battery (°C)', get: (x) => num(x.battery_temp_c) },
            ])}
          >
            <TimeChart
              data={windowFrames}
              series={[
                { key: 'bus_temp_c', label: 'Bus', color: SERIES[1] },
                { key: 'battery_temp_c', label: 'Battery', color: SERIES[2] },
              ]}
              limits={limitLines(config?.limits, 'battery_temp_c').filter((l) => l.value > 10)}
              shade={eclipses}
              unit="°C"
              xFormatter={missionTime}
              xDomain={xDomain}
            />
          </ChartCard>
        </div>
        <aside className="side-column">
          <AlertsPanel alerts={alerts} />
          <ResidualPanel latest={latest} />
          <FaultPanel catalog={catalog} faults={latest.faults} />
          <ValidationCard report={validation} />
        </aside>
      </div>
    </div>
  )
}
