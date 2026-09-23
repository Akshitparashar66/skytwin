import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export function CardHeader({
  title,
  icon,
  subtitle,
  meta,
}: {
  title: string
  icon?: IconName
  subtitle?: string
  meta?: ReactNode
}) {
  return (
    <header className="card-header">
      <div className="card-title-block">
        <h3 className="card-title">
          {icon && <Icon name={icon} size={16} className="card-icon" />}
          {title}
        </h3>
        {subtitle && <p className="card-subtitle">{subtitle}</p>}
      </div>
      {meta && <div className="card-meta">{meta}</div>}
    </header>
  )
}
