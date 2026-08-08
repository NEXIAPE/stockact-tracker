/**
 * Componentes para mostrar datos CITADOS.
 *
 * Regla del producto llevada al frontend: no existe forma de pintar un número
 * sin su fuente y su fecha. `<Datum>` sólo acepta los objetos que fabrica el
 * backend (`datapoint` o `missing`), y un dato faltante se pinta como faltante,
 * con su motivo, en vez de desaparecer o convertirse en un cero.
 */

export function Datum({ item }) {
  if (!item) return null

  if (item.kind === 'missing') {
    return (
      <div className="datum datum--missing">
        <span className="datum__label">{item.label}</span>
        <span className="datum__value">no disponible</span>
        <span className="datum__cite">
          {item.reason}
          {item.tried ? ` (se intentó: ${item.tried})` : ''}
        </span>
      </div>
    )
  }

  const stale = item.age_days > 45
  return (
    <div className="datum">
      <span className="datum__label">{item.label}</span>
      <span className="datum__value">{item.formatted}</span>
      <span className="datum__cite">
        {item.source_url ? (
          <a href={item.source_url} target="_blank" rel="noreferrer">
            {item.source_name}
          </a>
        ) : (
          item.source_name
        )}{' '}
        · dato al {item.as_of}
        {stale && <em className="stale"> · hace {item.age_days} días</em>}
      </span>
    </div>
  )
}

export function DatumList({ items, empty = 'Sin datos.' }) {
  if (!items?.length) return <p className="muted">{empty}</p>
  return (
    <div className="datum-list">
      {items.map((d, i) => (
        <Datum key={`${d.label}-${i}`} item={d} />
      ))}
    </div>
  )
}

export function Money({ value, fallback = 'no disponible' }) {
  if (value === null || value === undefined) return <span className="muted">{fallback}</span>
  return <span>US$ {Number(value).toLocaleString('es-PE', { maximumFractionDigits: 2 })}</span>
}

export function Pct({ value, digits = 1, fallback = '—' }) {
  if (value === null || value === undefined) return <span className="muted">{fallback}</span>
  return <span>{Number(value).toFixed(digits)} %</span>
}

export function Notice({ kind = 'info', title, children }) {
  return (
    <div className={`notice notice--${kind}`}>
      {title && <strong>{title}</strong>}
      <div>{children}</div>
    </div>
  )
}

export function Loading({ what = 'Cargando' }) {
  return <p className="muted">{what}…</p>
}

export function ErrorBox({ error }) {
  if (!error) return null
  const d = error.detail
  return (
    <div className="notice notice--error">
      <strong>No se pudo completar</strong>
      <div>{error.message}</div>
      {d?.sources_tried?.length > 0 && (
        <div className="muted">Fuentes intentadas: {d.sources_tried.join(', ')}</div>
      )}
      {d?.what_you_can_do && <div className="muted">{d.what_you_can_do}</div>}
    </div>
  )
}
