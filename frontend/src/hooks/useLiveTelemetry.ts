import { useEffect, useRef, useState } from 'react'
import { telemetrySocketUrl } from '../api'
import type { Alert, HistoryFrame, HistoryMessage, TelemetryMessage } from '../types'

export type ConnectionState = 'connecting' | 'open' | 'closed'

const MAX_FRAMES = 400
const MAX_ALERTS = 50

export interface LiveTelemetry {
  connection: ConnectionState
  latest: TelemetryMessage | null
  frames: HistoryFrame[]
  alerts: Alert[]
}

export function useLiveTelemetry(): LiveTelemetry {
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [latest, setLatest] = useState<TelemetryMessage | null>(null)
  const [frames, setFrames] = useState<HistoryFrame[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const retry = useRef(0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let timer: number | undefined
    let disposed = false

    const connect = () => {
      setConnection('connecting')
      ws = new WebSocket(telemetrySocketUrl())
      ws.onopen = () => {
        retry.current = 0
        setConnection('open')
      }
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data) as TelemetryMessage | HistoryMessage
        if (msg.type === 'history') {
          setFrames(msg.frames.slice(-MAX_FRAMES))
          setAlerts(msg.alerts.slice(0, MAX_ALERTS))
          return
        }
        setLatest(msg)
        const frame: HistoryFrame = { ...msg.frame, status: msg.status, anomaly_count: msg.anomalies.length }
        setFrames((prev) => [...prev.slice(-(MAX_FRAMES - 1)), frame])
        if (msg.new_alerts.length) {
          setAlerts((prev) => [...[...msg.new_alerts].reverse(), ...prev].slice(0, MAX_ALERTS))
        }
      }
      ws.onclose = () => {
        if (disposed) return
        setConnection('closed')
        const delay = Math.min(10000, 500 * 2 ** retry.current++)
        timer = window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      ws?.close()
    }
  }, [])

  return { connection, latest, frames, alerts }
}
