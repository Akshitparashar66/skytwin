import type { Anomaly, TelemetryMessage } from '../../types'
import { num, signed } from '../../lib/format'
import { STATUS } from '../../lib/colors'
import { CardHeader } from '../CardHeader'

const CHANNELS: { key: string; label: string; unit: string; digits: number }[] = [
  { key: 'solar_power_w', label: 'Solar power', unit: 'W', digits: 1 },
  { key: 'load_power_w', label: 'Load power', unit: 'W', digits: 1 },
  { key: 'battery_current_a', label: 'Battery current', unit: 'A', digits: 2 },
  { key: 'bus_temp_c', label: 'Bus temp', unit: '°C', digits: 2 },
  { key: 'battery_temp_c', label: 'Battery temp', unit: '°C', digits: 2 },
]

export function ResidualPanel({ latest }: { latest: TelemetryMessage | null }) {
  const anomalies = new Map<string, Anomaly>((latest?.anomalies ?? []).map((a) => [a.channel, a]))
  return (
    <section className="card">
      <CardHeader
        title="Twin vs telemetry"
        icon="chart"
        subtitle="Measured minus what the physics twin predicted one tick earlier"
        meta={<span className="count-pill">{anomalies.size ? `${anomalies.size} anomal${anomalies.size === 1 ? 'y' : 'ies'}` : 'in sync'}</span>}
      />
      <table className="data-table compact mono-nums">
        <thead>
          <tr>
            <th>Channel</th>
            <th className="num">Measured</th>
            <th className="num">Twin</th>
            <th className="num">Residual</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
          {CHANNELS.map((c) => {
            const measured = latest?.frame[c.key as keyof TelemetryMessage['frame']] as number | undefined
            const expected = latest?.expected[c.key]
            const anomaly = anomalies.get(c.key)
            return (
              <tr key={c.key}>
                <td>{c.label}</td>
                <td className="num">{num(measured, c.digits)}</td>
                <td className="num">{num(expected, c.digits)}</td>
                <td className="num">
                  {measured !== undefined && expected !== undefined ? signed(measured - expected, c.digits) : '—'} {c.unit}
                </td>
                <td>
                  {anomaly ? (
                    <span className="violation">
                      <span className="dot" style={{ background: STATUS.warning }} aria-hidden /> anomaly
                    </span>
                  ) : (
                    <span className="muted">
                      <span className="dot" style={{ background: STATUS.good }} aria-hidden /> ok
                    </span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
