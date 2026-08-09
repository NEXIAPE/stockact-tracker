/**
 * Gráfico de precio en SVG puro, sin librerías.
 *
 * Deliberadamente sobrio: una línea, su media de 200 días y las fechas. Sin
 * animaciones, sin degradados, sin flechas verdes y rojas gigantes. Un gráfico
 * dramático empuja a reaccionar, y reaccionar es justo lo que esta herramienta
 * intenta que hagas menos.
 *
 * Los puntos son cierres REALES submuestreados por el backend, nunca valores
 * promediados o interpolados, y el pie del gráfico cita siempre la fuente.
 */

import { useEffect, useState } from 'react'
import { api } from '../api.js'

const W = 640
const H = 180
const PAD = { top: 10, right: 8, bottom: 22, left: 46 }

export function PriceChart({ ticker, days = 365 }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivo = true
    setData(null)
    setError(null)
    api
      .priceSeries(ticker, days)
      .then((r) => vivo && setData(r))
      .catch((e) => vivo && setError(e))
    return () => {
      vivo = false
    }
  }, [ticker, days])

  if (error) {
    return (
      <p className="muted small">
        No se pudo dibujar el precio de {ticker}: {error.message}
      </p>
    )
  }
  if (!data) return <p className="muted small">Cargando el gráfico de {ticker}…</p>
  if (!data.points?.length) return <p className="muted small">Sin puntos que dibujar.</p>

  const closes = data.points.map((p) => p.c)
  const lo = Math.min(...closes, data.sma200 ?? Infinity)
  const hi = Math.max(...closes, data.sma200 ?? -Infinity)
  const span = hi - lo || 1
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom

  const x = (i) => PAD.left + (i / Math.max(1, data.points.length - 1)) * innerW
  const y = (v) => PAD.top + innerH - ((v - lo) / span) * innerH

  const linea = data.points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.c).toFixed(1)}`).join(' ')
  const area = `${linea} L${x(data.points.length - 1).toFixed(1)},${PAD.top + innerH} L${PAD.left},${PAD.top + innerH} Z`

  const primero = data.points[0]
  const ultimo = data.points[data.points.length - 1]
  const subio = ultimo.c >= primero.c

  const fmt = (v) => `US$ ${v.toLocaleString('es-PE', { maximumFractionDigits: 2 })}`

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart__svg" role="img"
           aria-label={`Precio de ${ticker} en los últimos ${days} días`}>
        {/* Rejilla mínima: sólo máximo y mínimo, para no ensuciar. */}
        {[hi, lo].map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="chart__grid" />
            <text x={PAD.left - 6} y={y(v) + 4} className="chart__axis" textAnchor="end">
              {v.toFixed(0)}
            </text>
          </g>
        ))}

        {data.sma200 != null && (
          <line
            x1={PAD.left} x2={W - PAD.right}
            y1={y(data.sma200)} y2={y(data.sma200)}
            className="chart__sma"
          />
        )}

        <path d={area} className={subio ? 'chart__area chart__area--up' : 'chart__area chart__area--down'} />
        <path d={linea} className={subio ? 'chart__line chart__line--up' : 'chart__line chart__line--down'} />

        <text x={PAD.left} y={H - 6} className="chart__axis">{primero.d}</text>
        <text x={W - PAD.right} y={H - 6} className="chart__axis" textAnchor="end">{ultimo.d}</text>
      </svg>

      <figcaption className="chart__cite">
        Cierre {fmt(data.last.close)} el {data.last.day}
        {data.sma200 != null ? ` · la línea discontinua es su media de 200 días` : ''}
        {data.sma200_missing ? ` · sin media de 200 días: ${data.sma200_missing}` : ''}
        {' · '}
        {data.source_url ? (
          <a href={data.source_url} target="_blank" rel="noreferrer">{data.source_name}</a>
        ) : (
          data.source_name
        )}
      </figcaption>
    </figure>
  )
}
