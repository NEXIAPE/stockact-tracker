/** Briefing diario: lo primero que ves al abrir. */

import { useEffect, useRef, useState } from 'react'
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
  // Tres peticiones compiten por pintar. El contador descarta las respuestas
  // de una carga que ya fue sustituida por otra más nueva.
  const cargaActual = useRef(0)

  // El briefing se carga en TRES tiempos, del dato más barato al más caro.
  //
  //   1. Local: alertas sin leer y tesis pendientes. Están en tu disco, no
  //      necesitan red y aparecen al instante.
  //   2. Valorado: la cartera con precios reales y los desvíos frente a tu
  //      plan. Medido con la red caída, esto tardaba 27 segundos, y hasta
  //      entonces la pestaña estaba en blanco.
  //   3. Ideas: analizan varios candidatos enteros (precio, fundamentales,
  //      noticias) y son lo que más tarda.
  //
  // Mientras falta la fase 2, la pantalla NO dice «hoy no hay nada que hacer»:
  // sin precios no se han podido comprobar los desvíos, y afirmar que no hay
  // nada habiendo mirado la mitad sería mentir para parecer rápido.
  const load = () => {
    const generacion = ++cargaActual.current
    let yaValorado = false
    setLoading(true)
    setIdeas(null)
    setIdeaProblems([])

    const fallo = (err) => {
      if (generacion !== cargaActual.current) return
      if (err.status === 409) navigate('/perfil')
      else setError(err)
    }

    api
      .briefing(false, false)
      .then((d) => {
        if (generacion !== cargaActual.current || yaValorado) return
        setData(d)
      })
      .catch(fallo)
      .finally(() => generacion === cargaActual.current && setLoading(false))

    api
      .briefing(false, true)
      .then((d) => {
        if (generacion !== cargaActual.current) return
        yaValorado = true
        setData(d)
        setLoading(false)
      })
      .catch(fallo)

    api
      .ideas(3)
      .then((r) => {
        if (generacion !== cargaActual.current) return
        setIdeas(r.ideas)
        setIdeaProblems(r.problems || [])
      })
      .catch(() => generacion === cargaActual.current && setIdeas([]))
  }

  useEffect(load, [])

  if (loading) return <Loading what="Abriendo tu briefing" />
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
            {p.prices_pending
              ? 'Consultando los precios para valorar tu cartera…'
              : 'No se pudo valorar tu cartera porque faltan precios. No muestro un total ' +
                'parcial haciéndolo pasar por completo.'}
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

  // «comprobando» comparte el gris neutro de «empezar»: no es una buena
  // noticia ni un aviso, es que todavía no se sabe. Pintarlo verde seria
  // insinuar calma antes de haber mirado.
  const clase =
    today.status === 'nada_que_hacer'
      ? 'today today--calm'
      : today.status === 'empezar' || today.status === 'comprobando'
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
