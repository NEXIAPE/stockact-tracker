/** Briefing diario: lo primero que ves al abrir. */

import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { DatumList, ErrorBox, Loading, Money, Notice, Pct } from '../components/Data.jsx'
import { RecommendationCard } from '../components/Recommendation.jsx'

export default function Briefing() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [ideas, setIdeas] = useState(null)     // null = todavia cargando
  const [ideaProblems, setIdeaProblems] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  // El briefing se carga en dos tiempos a proposito. Lo tuyo — cartera, alertas
  // y desvios — depende de pocas consultas y aparece enseguida. Las ideas exigen
  // analizar varios candidatos enteros (precio, fundamentales, noticias) y pueden
  // tardar bastante la primera vez. Bloquear toda la pagina por ellas dejaba una
  // pestana en blanco durante casi un minuto sin explicar nada.
  const load = () => {
    setLoading(true)
    setIdeas(null)
    setIdeaProblems([])

    api
      .briefing(false)
      .then(setData)
      .catch((err) => {
        if (err.status === 409) navigate('/perfil')
        else setError(err)
      })
      .finally(() => setLoading(false))

    api
      .ideas(3)
      .then((r) => {
        setIdeas(r.ideas)
        setIdeaProblems(r.problems || [])
      })
      .catch(() => setIdeas([]))
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

      <TodayCard today={data.today} />

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

      {/* Sólo los desvíos que NO están ya arriba como alerta: repetir la misma
          información con las mismas cifras dos veces seguidas duplicaba el
          largo de la página sin añadir nada. */}
      {data.deviations.some((d) => !d.already_alerted) && (
        <section className="card">
          <h2>Otros detalles de tu cartera</h2>
          {data.deviations
            .filter((d) => !d.already_alerted)
            .map((d, i) => (
              <div key={i} className="deviation">
                <span className={`tag tag--${d.severity === 'atencion' ? 'warn' : 'sm'}`}>
                  {d.label ?? d.kind}
                </span>
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
        {ideas === null ? (
          <Notice kind="calm">
            Analizando candidatos: precio, fundamentales y noticias de cada uno. La primera
            vez tarda hasta un minuto porque se consultan las fuentes de una en una para no
            abusar de servicios gratuitos. Después queda en caché y es inmediato. Mientras
            tanto, lo de arriba ya está listo.
          </Notice>
        ) : ideas.length > 0 ? (
          <>
            {ideas.length > 1 && <Notice kind="info">{data.ideas_sizing_notice}</Notice>}
            {ideas.map((idea) => (
              <RecommendationCard key={idea.ticker} rec={idea} compact />
            ))}
          </>
        ) : (
          <p className="muted">
            No hay ideas para mostrar hoy. Puede ser porque aún no registraste cartera ni
            watchlist, o porque las fuentes de datos no respondieron.
          </p>
        )}
        {ideaProblems.length > 0 && (
          <>
            <p className="muted small">Candidatos que no se pudieron analizar:</p>
            <ul className="small gaps">
              {ideaProblems.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </>
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

function TodayCard({ today }) {
  if (!today) return null

  const clase =
    today.status === 'nada_que_hacer'
      ? 'today today--calm'
      : today.status === 'empezar'
        ? 'today today--start'
        : 'today today--look'

  return (
    <section className={clase}>
      <h2 className="today__headline">{today.headline}</h2>
      <p className="today__explain">{today.explanation}</p>
      {today.items.length > 0 && (
        <ul className="today__items">
          {today.items.map((i, n) => (
            <li key={n}>
              <Link to={i.where}>{i.text}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
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
