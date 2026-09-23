import { useMemo } from 'react'
import { CardHeader } from '../CardHeader'
import { Icon } from '../Icon'
import type { Finding, Limit, SimulationResult } from '../../types'
import { BASELINE, SERIES, STATUS } from '../../lib/colors'
import { duration, missionTime, num, relTick } from '../../lib/format'
import { limitLines, mergeSimulation } from '../../lib/series'
import { ChartCard } from '../ChartCard'
import { StatusBadge, severityColor } from '../StatusBadge'
import { TimeChart } from '../TimeChart'
import { ImpactChain } from './ImpactChain'

interface ChartDef {
  channel: string
  title: string
  unit: string
  digits: number
  yDomain?: [number | 'auto', number | 'auto']
  limitFilter?: (value: number) => boolean
}

const CHARTS: ChartDef[] = [
  { channel: 'soc_pct', title: 'Battery state of charge', unit: '%', digits: 1, yDomain: [0, 100] },
  { channel: 'power_margin_w', title: 'Power margin (solar − load)', unit: 'W', digits: 1 },
  { channel: 'battery_temp_c', title: 'Battery temperature', unit: '°C', digits: 1, limitFilter: (v) => v > 10 },
  { channel: 'bus_temp_c', title: 'Bus temperature', unit: '°C', digits: 1, limitFilter: (v) => v > 10 },
  { channel: 'data_buffer_mb', title: 'Onboard data backlog', unit: 'MB', digits: 1, yDomain: [0, 'auto'] },
]

function findingText(f: Finding): string {
  if (f.channel === 'mode') return `Onboard SAFE mode${f.reason ? ` (${f.reason})` : ''}`
  const limit = f.limit === null ? '' : ` ${f.bound === 'low' ? '<' : '>'} ${f.limit}${f.unit === '%' ? '%' : ` ${f.unit}`}`
  return `${f.label}${limit}`
}

export function RiskBanner({ result, accent }: { result: SimulationResult; accent?: string }) {
  const s = result.summary
  return (
    <section className="card risk-banner" style={accent ? { borderTopColor: accent } : undefined}>
      <StatusBadge level={result.risk_level} size="lg" />
      <div className="risk-text">
        <div className="risk-title">{result.label}</div>
        <div className="muted small">
          Starting from the live state at {missionTime(result.start_t_min)} · horizon {duration(result.horizon_min)}
        </div>
      </div>
      <dl className="risk-facts">
        <div>
          <dt>Time to SOC critical</dt>
          <dd>{s.endurance_h === null ? 'sustainable' : `${duration(s.endurance_h * 60)}${s.endurance_basis === 'extrapolated' ? ' (trend)' : ''}`}</dd>
        </div>
        <div>
          <dt>SAFE mode</dt>
          <dd>{s.safe_mode_at_min === null ? 'not triggered' : `at T+${duration(s.safe_mode_at_min)}`}</dd>
        </div>
        {s.recovery_applicable && (
          <div>
            <dt>Recovery</dt>
            <dd>{s.recovery_min === null ? 'not within horizon' : `${duration(s.recovery_min)} after event`}</dd>
          </div>
        )}
      </dl>
    </section>
  )
}

function FindingsTable({ findings }: { findings: Finding[] }) {
  return (
    <section className="card">
      <CardHeader
        title="Identified risks"
        icon="warning"
        subtitle="Likely = nominal prediction · possible = only within the uncertainty band"
        meta={<span className="count-pill">{findings.length} total</span>}
      />
      {findings.length === 0 ? (
        <p className="muted small">No limit crossings predicted, including across the uncertainty ensemble.</p>
      ) : (
        <table className="data-table compact">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Condition</th>
              <th className="num">First at</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f, i) => (
              <tr key={i}>
                <td>
                  <span className="violation">
                    <span className="dot" style={{ background: severityColor(f.severity) }} aria-hidden /> {f.severity}
                  </span>
                </td>
                <td>
                  {findingText(f)}
                  {f.pre_existing && <span className="muted small"> · also without scenario</span>}
                </td>
                <td className="num">T+{duration(f.first_crossing_min)}</td>
                <td>{f.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

export function CommandBar() {
  return (
    <section className="card command-bar">
      <div className="command-text">
        <strong>Simulate → Evaluate → Operator decides.</strong>
        <p className="muted small">
          What-If runs on a copy of the twin. Nothing here changes the live model or reaches the spacecraft. Real commands go through
          the ground segment after review.
        </p>
      </div>
      <button className="button locked" disabled title="Simulation sandbox: commands are never sent from What-If mode" aria-disabled>
        <Icon name="lock" size={14} /> Send to spacecraft
      </button>
    </section>
  )
}

function SimChart({ result, def, limits }: { result: SimulationResult; def: ChartDef; limits?: Limit[] }) {
  const data = useMemo(() => mergeSimulation(result, def.channel), [result, def.channel])
  const lines = limitLines(limits, def.channel).filter((l) => (def.limitFilter ? def.limitFilter(l.value) : true))
  const safeAt = result.summary.safe_mode_at_min
  const step = Math.max(1, Math.ceil(data.length / 24))
  return (
    <ChartCard
      title={def.title}
      legend={[
        { label: 'Predicted', color: SERIES[1] },
        { label: 'Uncertainty band', color: SERIES[1], kind: 'band' },
        { label: 'Baseline (no change)', color: BASELINE },
      ]}
      table={{
        columns: ['T+', `Baseline (${def.unit})`, `Predicted (${def.unit})`, 'Band'],
        rows: data
          .filter((_, i) => i % step === 0)
          .map((r) => {
            const band = r.band as [number, number] | null
            return [
              duration(r.t_min as number),
              num(r.baseline as number, def.digits),
              num(r.predicted as number, def.digits),
              band ? `${num(band[0], def.digits)}–${num(band[1], def.digits)}` : '—',
            ]
          }),
      }}
    >
      <TimeChart
        data={data}
        series={[
          { key: 'baseline', label: 'Baseline', color: BASELINE, width: 1.5 },
          { key: 'predicted', label: 'Predicted', color: SERIES[1] },
        ]}
        band={{ key: 'band', label: 'Uncertainty', color: SERIES[1] }}
        limits={lines}
        unit={def.unit}
        digits={def.digits}
        xFormatter={relTick}
        yDomain={def.yDomain}
        markers={safeAt !== null ? [{ x: safeAt, label: 'SAFE', color: STATUS.critical }] : []}
      />
    </ChartCard>
  )
}

export function ResultView({ result, limits }: { result: SimulationResult; limits?: Limit[] }) {
  const showBacklog = result.impacts.some((i) => i.key === 'max_data_buffer_mb' && i.direction !== 'flat')
  const charts = CHARTS.filter((c) => c.channel !== 'data_buffer_mb' || showBacklog)
  return (
    <div className="result">
      <RiskBanner result={result} />
      <div className="result-grid">
        <ImpactChain impacts={result.impacts} />
        <section className="card">
          <CardHeader title="What the twin predicts" icon="bulb" />
          <ul className="narrative">
            {result.narrative.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <h4 className="subhead">Recommendations</h4>
          <ol className="recommendations">
            {result.recommendations.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ol>
        </section>
      </div>
      <div className="chart-grid">
        {charts.map((def) => (
          <SimChart key={def.channel} result={result} def={def} limits={limits} />
        ))}
      </div>
      <FindingsTable findings={result.findings} />
      <CommandBar />
    </div>
  )
}
