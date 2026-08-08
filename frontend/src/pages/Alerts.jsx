/** Alertas: cosas que vale la pena mirar. Nunca urgencias. */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { DatumList, ErrorBox, Loading, Notice } from '../components/Data.jsx'

const KIND_LABEL = {
  noticia: 'Noticia',
  precio: 'Movimiento de precio',
  criterio: 'Criterio tuyo',
  cartera: 'Tu cartera',
}

export default function Alerts() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState([])
  const [framing, setFraming] = useState('')
  const [refreshResult, setRefreshResult] = useState(null)
  const [onlyUnread, setOnlyUnread] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = (unread = onlyUnread) => {
    setLoading(true)
    api
      .alerts(unread)
      .then((r) => {
        setAlerts(r.alerts)
        setFraming(r.framing)
      })
      .catch((err) => (err.status === 409 ? navigate('/perfil') : setError(err)))
      .finally(() => setLoading(false))
  }

  useEffect(() => load(), [onlyUnread])

  const refresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      setRefreshResult(await api.refreshAlerts())
      load()
    } catch (err) {
      setError(err)
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className="page">
      <header className="page__head">
        <h1>Alertas</h1>
        <div className="row">
          <label className="inline">
            <input type="checkbox" checked={onlyUnread} onChange={(e) => setOnlyUnread(e.target.checked)} />
            Sólo sin leer
          </label>
          <button onClick={() => api.markAllRead().then(() => load())}>Marcar todas leídas</button>
          <button className="primary" onClick={refresh} disabled={refreshing}>
            {refreshing ? 'Revisando…' : 'Revisar ahora'}
          </button>
        </div>
      </header>

      <Notice kind="calm">{framing}</Notice>
      <ErrorBox error={error} />

      {refreshResult && (
        <section className="card">
          <p>
            Revisé {refreshResult.checked_tickers.length} símbolo(s) y encontré{' '}
            {refreshResult.new} alerta(s) nueva(s).
          </p>
          {refreshResult.problems?.length > 0 && (
            <>
              <p className="muted small">Lo que no pude comprobar:</p>
              <ul className="small gaps">
                {refreshResult.problems.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {loading ? (
        <Loading what="Cargando alertas" />
      ) : !alerts.length ? (
        <p className="muted">
          No hay alertas. Eso es lo normal la mayoría de los días, y es una buena señal.
        </p>
      ) : (
        <ul className="alerts">
          {alerts.map((a) => (
            <li key={a.id} className={a.read ? 'read' : ''}>
              <div className="alert__head">
                <span className="tag tag--sm">{KIND_LABEL[a.kind] ?? a.kind}</span>
                <strong>{a.title}</strong>
                {!a.read && (
                  <button className="linkish" onClick={() => api.markRead(a.id).then(() => load())}>
                    marcar leída
                  </button>
                )}
              </div>
              <p className="small">{a.body}</p>
              <DatumList items={a.evidence} empty="" />
              <span className="muted small">{a.created_at}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
