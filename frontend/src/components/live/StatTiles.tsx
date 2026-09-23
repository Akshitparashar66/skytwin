import type { Frame, LimitViolation } from '../../types'
import { num } from '../../lib/format'
import { Icon, type IconName } from '../Icon'
import { severityColor } from '../StatusBadge'

interface TileSpec {
  channel?: string
  label: string
  icon: IconName
  value: string
  unit?: string
  hint?: string
  tone?: 'good' | 'bad'
}

function tiles(f: Frame, capacityWh: number): TileSpec[] {
  return [
    {
      channel: 'soc_pct',
      label: 'Battery SOC',
      icon: 'battery',
      value: num(f.soc_pct, 1),
      unit: '%',
      hint: `${num((f.soc_pct / 100) * capacityWh, 0)} Wh stored`,
    },
    {
      channel: 'battery_voltage_v',
      label: 'Battery voltage',
      icon: 'bolt',
      value: num(f.battery_voltage_v, 2),
      unit: 'V',
      hint: `${f.battery_current_a >= 0 ? 'discharging' : 'charging'} ${num(Math.abs(f.battery_current_a), 2)} A`,
    },
    {
      label: 'Power margin',
      icon: 'trend',
      value: `${f.power_margin_w >= 0 ? '+' : ''}${num(f.power_margin_w, 1)}`,
      unit: 'W',
      hint: `solar ${num(f.solar_power_w, 0)} W · load ${num(f.load_power_w, 0)} W`,
      tone: f.power_margin_w >= 0 ? 'good' : undefined,
    },
    {
      channel: 'battery_temp_c',
      label: 'Battery temp',
      icon: 'thermo',
      value: num(f.battery_temp_c, 1),
      unit: '°C',
      hint: f.heater_on ? 'heater on' : 'heater off',
    },
    { channel: 'bus_temp_c', label: 'Bus temp', icon: 'thermo', value: num(f.bus_temp_c, 1), unit: '°C', hint: 'avionics bus' },
    {
      channel: 'data_buffer_pct',
      label: 'Data backlog',
      icon: 'database',
      value: num(f.data_buffer_mb, 1),
      unit: 'MB',
      hint: f.link_up ? 'link up' : 'link down',
    },
  ]
}

export function StatTiles({ frame, violations, capacityWh }: { frame: Frame; violations: LimitViolation[]; capacityWh: number }) {
  return (
    <div className="stat-tiles">
      {tiles(frame, capacityWh).map((t) => {
        const v = violations.find((x) => x.channel === t.channel)
        return (
          <div key={t.label} className="stat-tile" style={v ? { borderColor: severityColor(v.severity) } : undefined}>
            <div className="stat-head">
              <span className="stat-label">{t.label}</span>
              <Icon name={t.icon} size={16} className="stat-icon" />
            </div>
            <div className={`stat-value ${t.tone === 'good' ? 'tone-good' : ''}`}>
              {t.value}
              {t.unit && <span className="stat-unit">{t.unit}</span>}
            </div>
            <div className="stat-hint">
              {v ? (
                <span className="violation">
                  <span className="dot" style={{ background: severityColor(v.severity) }} aria-hidden /> {v.severity} limit {v.limit}
                  {v.unit === '%' ? '%' : ` ${v.unit}`}
                </span>
              ) : (
                t.hint
              )}
            </div>
          </div>
        )
      })}
      <div className="stat-tile">
        <div className="stat-head">
          <span className="stat-label">Operating mode</span>
          <Icon name="cpu" size={16} className="stat-icon" />
        </div>
        <div className="stat-value">
          <span className={`mode-pill ${frame.mode === 'SAFE' ? 'mode-safe' : 'mode-nominal'}`}>{frame.mode}</span>
        </div>
        <div className="stat-hint">{frame.mode === 'SAFE' ? frame.safe_mode_reason : `payload ${frame.payload_on ? 'on' : 'off'}`}</div>
      </div>
    </div>
  )
}
