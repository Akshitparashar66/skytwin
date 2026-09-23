import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImpactChain } from './ImpactChain'
import type { Impact } from '../../types'

const impacts: Impact[] = [
  { key: 'min_soc_pct', label: 'Battery SOC (min)', unit: '%', baseline: 70.1, predicted: 42.4, delta: -27.7, direction: 'down', effect: 'worse' },
  { key: 'endurance_h', label: 'Time to SOC critical', unit: 'h', baseline: null, predicted: 7.7, delta: null, direction: 'down', effect: 'worse' },
  { key: 'max_data_buffer_mb', label: 'Data backlog', unit: 'MB', baseline: 0, predicted: 0, delta: 0, direction: 'flat', effect: 'neutral' },
]

describe('ImpactChain', () => {
  it('lists changed metrics with direction, values and effect as text', () => {
    render(<ImpactChain impacts={impacts} />)
    expect(screen.getByText(/Battery SOC \(min\)/)).toBeInTheDocument()
    expect(screen.getByText('42.4%')).toBeInTheDocument()
    expect(screen.getByText('sustainable')).toBeInTheDocument()
    expect(screen.getAllByText('worse')).toHaveLength(2)
    expect(screen.getAllByLabelText('decreases')).toHaveLength(2)
  })

  it('summarises unchanged metrics', () => {
    render(<ImpactChain impacts={impacts} />)
    expect(screen.getByText(/Unchanged: data backlog/)).toBeInTheDocument()
  })
})
