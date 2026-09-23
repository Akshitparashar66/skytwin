import type { ValidationReport } from '../../types'
import { pct } from '../../lib/format'
import { CardHeader } from '../CardHeader'

export function ValidationCard({ report }: { report: ValidationReport | null }) {
  if (!report) return null
  if (!report.available || !report.methods?.length) {
    return (
      <section className="card">
        <CardHeader title="Anomaly detector benchmark" icon="chart" />
        <p className="muted small">
          Not run yet. <code>python scripts/download_nasa.py</code> then <code>python scripts/validate_anomalies.py</code>.
        </p>
      </section>
    )
  }
  const bestF1 = Math.max(...report.methods.map((m) => m.msl_held_out.f1))
  const lstm = report.methods.find((m) => m.id === 'lstm')
  return (
    <section className="card">
      <CardHeader
        title="Anomaly detector benchmark"
        icon="chart"
        subtitle="Real labelled anomalies from NASA's SMAP satellite and MSL Curiosity rover"
        meta={<span className="count-pill">MSL held out</span>}
      />
      <table className="data-table compact mono-nums">
        <thead>
          <tr>
            <th>Detector</th>
            <th className="num">Detected</th>
            <th className="num">Precision</th>
            <th className="num">Recall</th>
            <th className="num">F1</th>
          </tr>
        </thead>
        <tbody>
          {report.methods.map((m) => {
            const best = m.msl_held_out.f1 === bestF1 && report.methods.length > 1
            return (
              <tr key={m.id} className={best ? 'row-best' : undefined}>
                <td title={m.description}>
                  {m.id === 'lstm' ? 'LSTM' : m.id === 'statistical' ? 'Statistical' : m.name}
                  {best && <span className="best-tag">best</span>}
                </td>
                <td className="num">
                  {m.msl_held_out.true_positives}/{m.msl_held_out.labelled_anomalies}
                </td>
                <td className="num">{pct(m.msl_held_out.precision)}</td>
                <td className="num">{pct(m.msl_held_out.recall)}</td>
                <td className="num">{m.msl_held_out.f1.toFixed(2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="muted small">
        Thresholds and model choice use SMAP only; MSL is never seen during tuning.
        {lstm?.model
          ? ` LSTM: ${lstm.model.layers}×${lstm.model.hidden}, window ${lstm.model.window}${lstm.model.horizon ? `, predicts ${lstm.model.horizon} steps ahead` : ''}, trained on unlabelled nominal telemetry.`
          : ' No trained model loaded. See training/README.md.'}
      </p>
    </section>
  )
}
