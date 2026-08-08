/** Briefing diario: lo primero que ves al abrir. */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { DatumList, ErrorBox, Loading, Money, Notice, Pct } from '../components/Data.jsx'
import { RecommendationCard } from '../components/Recommendation.jsx'

export default function Briefing() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    api
      .briefing()
      .then(setData)
      .catch((err) => {
        if (err.status === 409) navigate('/perfil')
        else setError(err)
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return <Loading what="Preparando tu briefing (consultando precios reales)" />
  if (error) return <ErrorBox error={error} />
  if (!data) return null

  const p = data.portfolio

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Tu briefing</h1>
          <p className="muted">{data.date}</p>
        </div>
        <button onClick={load}>Actualizar</button>
      </header>

      <Notice kind="calm">{data.headline}</Notice>

      <section className="card">
        <h2>Cómo va tu cartera</h2>
        {p.total_value === null ? (
          <p className="muted">
            No se pudo valorar tu cartera porque faltan precios. No muestro un total parcial
            haciéndolo pasar por completo.
          </p>
        ) : (
          <div className="grid">
            <Stat label="Valor total" value={<Money value={p.total_value} />} />
            <Stat label="Invertido" value={<Money value={p.invested_value} />} />
            <Stat label="Efectivo" value={<Money value={p.cash} />} />
            <Stat label="En acciones" value={<Pct value={p.stocks_vs_bonds.acciones} />} />
            <Stat label="En bonos" value={<Pct value={p.stocks_vs_bonds.bonos} />} />
            <Stat label="En acciones sueltas" value={<Pct value={p.individual_stock_pct} />} />
          </div>
        )}
        {p.data_warning && <Notice kind="warn">{p.data_warning}</Notice>}
        <Link to="/cartera">Ver mi cartera en detalle →</Link>
      </section>

      <section className="card">
        <h2>Alertas sin leer ({data.unread_alerts.length})</h2>
        {!data.unread_alerts.length ? (
          <p className="muted">Nada pendiente. Un día tranquilo es una buena noticia.</p>
        ) : (
          <ul className="alerts">
            {data.unread_alerts.map((a) => (
              <li key={a.id}>
                <span className="tag tag--sm">{a.kind}</span> <strong>{a.title}</strong>
                <p className="small">{a.body}</p>
                <DatumList items={a.evidence} empty="" />
              </li>
            ))}
          </ul>
        )}
        <Link to="/alertas">Ver todas las alertas →</Link>
      </section>

      {data.deviations.length > 0 && (
        <section className="card">
          <h2>Tu cartera frente a tu estrategia</h2>
          {data.deviations.map((d, i) => (
            <div key={i} className="deviation">
              <span className={`tag tag--${d.severity === 'atencion' ? 'warn' : 'sm'}`}>{d.kind}</span>
              <p>{d.message}</p>
              <DatumList items={d.numbers} empty="" />
            </div>
          ))}
        </section>
      )}

      <section className="card">
        <h2>Ideas que encajan con tu perfil</h2>
        <p className="muted small">
          Puntos de partida para investigar, no una lista de compras. Ninguna requiere que
          hagas nada hoy.
        </p>
        {data.ideas.length > 1 && <Notice kind="info">{data.ideas_sizing_notice}</Notice>}
        {!data.ideas.length ? (
          <p className="muted">
            No hay ideas para mostrar hoy. Puede ser porque aún no registraste cartera ni
            watchlist, o porque las fuentes de datos no respondieron.
          </p>
        ) : (
          data.ideas.map((idea) => <RecommendationCard key={idea.ticker} rec={idea} compact />)
        )}
      </section>

      <section className="card">
        <h2>Estado de los datos</h2>
        <p className="muted small">
          Lo que la herramienta NO pudo saber hoy. Prefiero que lo sepas a que asumas que
          está todo cubierto.
        </p>
        {!data.data_health.length ? (
          <p className="muted">Todas las fuentes respondieron.</p>
        ) : (
          <ul className="small gaps">
            {data.data_health.map((h, i) => (
              <li key={i}>{h}</li>
            ))}
          </ul>
        )}
      </section>

      <div className="disclaimers">
        <p>{data.notices.no_rush}</p>
        <p>{data.notices.read_only}</p>
        <p>{data.notices.not_advice}</p>
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
    </div>
  )
}
