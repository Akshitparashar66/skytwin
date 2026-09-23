import { STATUS } from '../lib/colors'

type Level = 'NOMINAL' | 'CAUTION' | 'WARNING' | 'CRITICAL'

const STYLE: Record<Level, { color: string; icon: string }> = {
  NOMINAL: { color: STATUS.good, icon: '✓' },
  CAUTION: { color: STATUS.serious, icon: '?' },
  WARNING: { color: STATUS.warning, icon: '!' },
  CRITICAL: { color: STATUS.critical, icon: '✕' },
}

export function StatusBadge({ level, size = 'md' }: { level: Level; size?: 'md' | 'lg' }) {
  const { color, icon } = STYLE[level]
  return (
    <span className={`status-badge ${size}`} style={{ borderColor: color }}>
      <span className="status-icon" style={{ background: color }} aria-hidden>
        {icon}
      </span>
      {level}
    </span>
  )
}

export function severityColor(severity: 'warning' | 'critical'): string {
  return severity === 'critical' ? STATUS.critical : STATUS.warning
}
