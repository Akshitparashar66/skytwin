import { useState, type ReactNode } from 'react'

export interface LegendItem {
  label: string
  color: string
  kind?: 'line' | 'band' | 'limit'
}

interface Props {
  title: string
  subtitle?: string
  legend?: LegendItem[]
  table?: { columns: string[]; rows: (string | number)[][] }
  children: ReactNode
}

export function ChartCard({ title, subtitle, legend, table, children }: Props) {
  const [showTable, setShowTable] = useState(false)
  return (
    <section className="card chart-card">
      <header className="chart-card-header">
        <div className="card-title-block">
          <div className="chart-title-row">
            <h3 className="card-title">{title}</h3>
            {legend && legend.length > 0 && (
              <ul className="legend" aria-label="Legend">
                {legend.map((item) => (
                  <li key={item.label}>
                    <span
                      className={`legend-mark ${item.kind ?? 'line'}`}
                      style={{ background: item.color, borderColor: item.color }}
                    />
                    {item.label}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        {table && (
          <button className="ghost-button" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}>
            {showTable ? 'Chart' : 'Table'}
          </button>
        )}
      </header>
      {showTable && table ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {table.columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((cell, j) => (
                    <td key={j}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        children
      )}
    </section>
  )
}
