import { useMemo } from 'react'
import { CardHeader } from '../CardHeader'
import type { Limit, SimulationResult } from '../../types'
import { BASELINE, SERIES } from '../../lib/colors'
import { duration, num, relTick } from '../../lib/format'
import { limitLines, mergeComparison } from '../../lib/series'
import { ChartCard } from '../ChartCard'
import { TimeChart } from '../TimeChart'
import { impactValue } from './ImpactChain'
import { CommandBar, RiskBanner } from './ResultView'

const CHARTS = [
  { channel: 'soc_pct', title: 'Battery state of charge', unit: '%', digits: 1, yDomain: [0, 100] as [number, number] },
  { channel: 'power_margin_w', title: 'Power margin', unit: 'W', digits: 1 },
  { channel: 'battery_temp_c', title: 'Battery temperature', unit: '°C', digits: 1 },
]

export function CompareView({ a, b, limits }: { a: SimulationResult; b: SimulationResult; limits?: Limit[] }) {
  return (
    <div className="result">
      <div className="compare-banners">
        <RiskBanner result={a} accent={SERIES[1]} />
        <RiskBanner result={b} accent={SERIES[2]} />
      </div>
      <section className="card">
        <CardHeader title="Side by side" icon="compare" subtitle="Both runs start from the same live snapshot" />
        <table className="data-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="num">Baseline</th>
              <th className="num">
                <span className="swatch" style={{ background: SERIES[1] }} /> A
              </th>
              <th className="num">
                <span className="swatch" style={{ background: SERIES[2] }} /> B
              </th>
            </tr>
          </thead>
          <tbody>
            {a.impacts.map((ia) => {
              const ib = b.impacts.find((x) => x.key === ia.key)
              return (
                <tr key={ia.key}>
                  <td>{ia.label}</td>
                  <td className="num muted">{impactValue(ia, 'baseline')}</td>
                  <td className="num">{impactValue(ia, 'predicted')}</td>
                  <td className="num">{ib ? impactValue(ib, 'predicted') : ia.key === 'endurance_h' ? 'sustainable' : '—'}</td>
                </tr>
              )
            })}
            <tr>
              <td>Risks (likely)</td>
              <td className="num muted">—</td>
              <td className="num">{a.findings.filter((f) => f.confidence === 'likely').length}</td>
              <td className="num">{b.findings.filter((f) => f.confidence === 'likely').length}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <div className="chart-grid">
        {CHARTS.map((c) => (
          <CompareChart key={c.channel} a={a} b={b} def={c} limits={limits} />
        ))}
      </div>
      <CommandBar />
    </div>
  )
}

function CompareChart({
  a,
  b,
  def,
  limits,
}: {
  a: SimulationResult
  b: SimulationResult
  def: (typeof CHARTS)[number]
  limits?: Limit[]
}) {
  const data = useMemo(() => mergeComparison(a, b, def.channel), [a, b, def.channel])
  const step = Math.max(1, Math.ceil(data.length / 24))
  return (
    <ChartCard
      title={def.title}
      legend={[
        { label: `A: ${a.label}`, color: SERIES[1] },
        { label: `B: ${b.label}`, color: SERIES[2] },
        { label: 'Baseline', color: BASELINE },
      ]}
      table={{
        columns: ['T+', 'Baseline', 'A', 'B'],
        rows: data
          .filter((_, i) => i % step === 0)
          .map((r) => [duration(r.t_min as number), num(r.baseline as number), num(r.a as number), num(r.b as number)]),
      }}
    >
      <TimeChart
        data={data}
        series={[
          { key: 'baseline', label: 'Baseline', color: BASELINE, width: 1.5 },
          { key: 'a', label: 'A', color: SERIES[1] },
          { key: 'b', label: 'B', color: SERIES[2] },
        ]}
        limits={limitLines(limits, def.channel).filter((l) => def.channel !== 'battery_temp_c' || l.value > 10)}
        unit={def.unit}
        digits={def.digits}
        xFormatter={relTick}
        yDomain={'yDomain' in def ? def.yDomain : undefined}
      />
    </ChartCard>
  )
}
