import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { CHROME, STATUS } from '../lib/colors'
import type { LimitLine } from '../lib/series'

export interface SeriesSpec {
  key: string
  label: string
  color: string
  width?: number
}

export interface BandSpec {
  key: string
  label: string
  color: string
}

interface Props {
  data: object[]
  series: SeriesSpec[]
  band?: BandSpec
  limits?: LimitLine[]
  shade?: [number, number][]
  unit: string
  digits?: number
  xFormatter: (v: number) => string
  xDomain?: [number, number]
  yDomain?: [number | 'auto' | 'dataMin' | 'dataMax', number | 'auto' | 'dataMin' | 'dataMax']
  height?: number
  markers?: { x: number; label: string; color: string }[]
}

interface TooltipEntry {
  dataKey?: string | number
  value?: number | [number, number]
  color?: string
}

function ChartTooltip({
  active,
  payload,
  label,
  series,
  band,
  unit,
  digits,
  xFormatter,
}: {
  active?: boolean
  payload?: readonly TooltipEntry[]
  label?: number
  series: SeriesSpec[]
  band?: BandSpec
  unit: string
  digits: number
  xFormatter: (v: number) => string
}) {
  if (!active || !payload?.length || label === undefined) return null
  const byKey = new Map(payload.map((p) => [String(p.dataKey), p.value]))
  const bandValue = band ? byKey.get(band.key) : undefined
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{xFormatter(label)}</div>
      {series.map((s) => {
        const v = byKey.get(s.key)
        if (typeof v !== 'number') return null
        return (
          <div key={s.key} className="chart-tooltip-row">
            <span className="swatch" style={{ background: s.color }} />
            <span className="chart-tooltip-label">{s.label}</span>
            <span className="chart-tooltip-value">
              {v.toFixed(digits)} {unit}
            </span>
          </div>
        )
      })}
      {Array.isArray(bandValue) && (
        <div className="chart-tooltip-row muted">
          <span className="swatch band" />
          <span className="chart-tooltip-label">{band!.label}</span>
          <span className="chart-tooltip-value">
            {bandValue[0].toFixed(digits)}–{bandValue[1].toFixed(digits)} {unit}
          </span>
        </div>
      )}
    </div>
  )
}

export function TimeChart({
  data,
  series,
  band,
  limits = [],
  shade = [],
  unit,
  digits = 1,
  xFormatter,
  xDomain,
  yDomain = ['auto', 'auto'],
  height = 200,
  markers = [],
}: Props) {
  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 44, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHROME.grid} vertical={false} />
          {shade.map(([x1, x2]) => (
            <ReferenceArea key={`${x1}-${x2}`} x1={x1} x2={x2} fill={CHROME.eclipse} strokeOpacity={0} ifOverflow="hidden" />
          ))}
          <XAxis
            dataKey="t_min"
            type="number"
            domain={xDomain ?? ['dataMin', 'dataMax']}
            tickFormatter={xFormatter}
            stroke={CHROME.axis}
            tick={{ fill: CHROME.muted, fontSize: 11 }}
            tickLine={false}
            minTickGap={40}
            allowDataOverflow
          />
          <YAxis
            domain={yDomain}
            stroke={CHROME.axis}
            tick={{ fill: CHROME.muted, fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={48}
            tickFormatter={(v: number) => `${Number.isInteger(v) ? v : v.toFixed(1)}`}
            allowDataOverflow={false}
          />
          {limits.map((l) => (
            <ReferenceLine
              key={`${l.severity}-${l.value}`}
              y={l.value}
              stroke={l.severity === 'critical' ? STATUS.critical : STATUS.warning}
              strokeDasharray="4 4"
              strokeWidth={1}
              ifOverflow="extendDomain"
              label={{
                value: `${l.label} ${l.value}`,
                position: 'right',
                fill: CHROME.muted,
                fontSize: 10,
              }}
            />
          ))}
          {markers.map((m) => (
            <ReferenceLine
              key={`m-${m.x}-${m.label}`}
              x={m.x}
              stroke={m.color}
              strokeWidth={1}
              label={{ value: m.label, position: 'insideTopLeft', fill: CHROME.muted, fontSize: 10 }}
            />
          ))}
          {band && (
            <Area
              dataKey={band.key}
              stroke="none"
              fill={band.color}
              fillOpacity={0.18}
              isAnimationActive={false}
              activeDot={false}
            />
          )}
          {series.map((s) => (
            <Line
              key={s.key}
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={s.width ?? 2}
              dot={false}
              activeDot={{ r: 4, stroke: '#ffffff', strokeWidth: 2 }}
              isAnimationActive={false}
              connectNulls
            />
          ))}
          <Tooltip
            cursor={{ stroke: CHROME.muted, strokeWidth: 1 }}
            content={(props) => (
              <ChartTooltip
                active={props.active}
                payload={props.payload as readonly TooltipEntry[] | undefined}
                label={props.label as number | undefined}
                series={series}
                band={band}
                unit={unit}
                digits={digits}
                xFormatter={xFormatter}
              />
            )}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
