import type { Catalog, KindSpec, PerturbationIn } from '../../types'
import { CardHeader } from '../CardHeader'

export interface ScenarioDraft {
  label?: string
  perturbations: PerturbationIn[]
}

interface Props {
  title: string
  catalog: Catalog
  value: ScenarioDraft
  onChange: (next: ScenarioDraft) => void
  accent: string
}

function defaultsFor(spec: KindSpec): PerturbationIn {
  return {
    kind: spec.kind,
    magnitude: spec.magnitude?.default ?? null,
    start_min: 0,
    duration_min: spec.requires_duration ? spec.default_duration_min : null,
  }
}

export function ScenarioBuilder({ title, catalog, value, onChange, accent }: Props) {
  const specs = new Map(catalog.kinds.map((k) => [k.kind, k]))

  const update = (i: number, patch: Partial<PerturbationIn>) =>
    onChange({
      label: undefined,
      perturbations: value.perturbations.map((p, j) => (j === i ? { ...p, ...patch } : p)),
    })

  return (
    <section className="card builder" style={{ borderTopColor: accent }}>
      <CardHeader title={title} icon="sim" subtitle="Pick a preset or edit the changes below" />

      <div className="presets" role="group" aria-label="Preset scenarios">
        {catalog.presets.map((preset) => (
          <button
            key={preset.id}
            className={`chip ${value.label === preset.label ? 'active' : ''}`}
            title={preset.description}
            onClick={() =>
              onChange({
                label: preset.label,
                perturbations: preset.perturbations.map(({ kind, magnitude, start_min, duration_min }) => ({
                  kind,
                  magnitude,
                  start_min,
                  duration_min,
                })),
              })
            }
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="perturbations">
        {value.perturbations.map((p, i) => {
          const spec = specs.get(p.kind)
          if (!spec) return null
          return (
            <div key={i} className="perturbation">
              <div className="perturbation-head">
                <select
                  aria-label="Change"
                  value={p.kind}
                  onChange={(e) => {
                    const next = specs.get(e.target.value)
                    if (next) update(i, defaultsFor(next))
                  }}
                >
                  {catalog.kinds.map((k) => (
                    <option key={k.kind} value={k.kind}>
                      {k.label}
                      {k.category === 'mitigation' ? ' (mitigation)' : ''}
                    </option>
                  ))}
                </select>
                <button
                  className="icon-button"
                  aria-label="Remove change"
                  disabled={value.perturbations.length === 1}
                  onClick={() => onChange({ label: undefined, perturbations: value.perturbations.filter((_, j) => j !== i) })}
                >
                  ×
                </button>
              </div>
              <p className="muted small">{spec.description}</p>
              {spec.magnitude && (
                <label className="field">
                  <span>
                    {spec.magnitude.label}: <strong>{p.magnitude ?? spec.magnitude.default}</strong> {spec.magnitude.unit}
                  </span>
                  <input
                    type="range"
                    min={spec.magnitude.min}
                    max={spec.magnitude.max}
                    step={1}
                    value={p.magnitude ?? spec.magnitude.default}
                    onChange={(e) => update(i, { magnitude: Number(e.target.value) })}
                  />
                </label>
              )}
              <div className="form-row">
                <label className="field">
                  <span>Starts at T+ (min)</span>
                  <input
                    type="number"
                    min={0}
                    max={1440}
                    value={p.start_min ?? 0}
                    onChange={(e) => update(i, { start_min: Math.max(0, Number(e.target.value)) })}
                  />
                </label>
                {!spec.impulse && (
                  <label className="field">
                    <span>Duration (min)</span>
                    <input
                      type="number"
                      min={1}
                      max={1440}
                      placeholder="persistent"
                      value={p.duration_min ?? ''}
                      onChange={(e) =>
                        update(i, {
                          duration_min:
                            e.target.value === '' ? (spec.requires_duration ? spec.default_duration_min : null) : Math.max(1, Number(e.target.value)),
                        })
                      }
                    />
                  </label>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {value.perturbations.length < 8 && (
        <button
          className="link-button"
          onClick={() =>
            onChange({
              label: undefined,
              perturbations: [...value.perturbations, defaultsFor(specs.get('payload_off') ?? catalog.kinds[0])],
            })
          }
        >
          + Add another change
        </button>
      )}
    </section>
  )
}
