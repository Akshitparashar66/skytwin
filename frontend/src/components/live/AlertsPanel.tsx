import type { Alert } from '../../types'
import { missionTime } from '../../lib/format'
import { CardHeader } from '../CardHeader'
import { Icon } from '../Icon'
import { severityColor } from '../StatusBadge'

const KIND_LABEL: Record<Alert['kind'], string> = {
  anomaly: 'Twin residual',
  limit: 'Limit',
  mode: 'Mode',
}

export function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="card">
      <CardHeader
        title="Alerts"
        icon="bell"
        meta={<span className={`count-pill ${alerts.length ? 'has-items' : ''}`}>{alerts.length ? `${alerts.length} recent` : '0 active'}</span>}
      />
      {alerts.length === 0 ? (
        <div className="empty-inline">
          <span className="empty-check">
            <Icon name="check" size={16} />
          </span>
          No alerts. Telemetry matches the twin.
        </div>
      ) : (
        <ul className="alert-list">
          {alerts.slice(0, 12).map((a) => (
            <li key={a.id} className="alert-item" style={{ borderLeftColor: severityColor(a.severity) }}>
              <div className="alert-meta">
                <span className="alert-severity" style={{ color: severityColor(a.severity) }}>
                  {a.severity}
                </span>
                <span className="alert-kind">{KIND_LABEL[a.kind]}</span>
                <span className="alert-time">{missionTime(a.t_min)}</span>
              </div>
              <div className="alert-message">{a.message}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
