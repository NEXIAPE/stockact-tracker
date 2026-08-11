/**
 * «Más barato que hace poco».
 *
 * NO se llama «oportunidades» a propósito: esa palabra afirma la conclusión
 * antes de mirar. Aquí sólo se muestra un hecho comprobable —cuánto ha caído
 * cada cosa respecto de su máximo del último año— y se deja la conclusión al
 * usuario. Ninguna previsión de recuperación aparece en esta pantalla.
 *
 * Los fondos amplios y las acciones sueltas van en bloques separados porque una
 * caída significa cosas distintas en cada caso. Mezclarlos sería la trampa.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Datum, ErrorBox, Loading, Notice, SafeLink } from '../components/Data.jsx'

export default function Cheaper() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setData(null)
    setError(null)
    api.cheaper().then(setData).catch(setError)
  }

  useEffect(load, [])

  if (error) return <ErrorBox error={error} />
  if (!data) return <Loading what="Mirando qué ha caído de tu universo" />

  const nada = !data.broad.length && !data.individual.length

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Más barato que hace poco</h1>
          <p className="muted">{data.as_of}</p>
        </div>
        <button onClick={load}>Actualizar</button>
      </header>

      <Notice kind="warn" title="Lo que esta pantalla NO dice">
        {data.no_forecast_notice}
      </Notice>

      <p className="lead">{data.scope_notice}</p>

      {nada ? (
        <section className="card">
          <p className="muted">{data.empty_notice}</p>
          <Link to="/watchlist">Añadir símbolos a mi watchlist →</Link>
        </section>
      ) : (
        <>
          <Group
            title="Fondos amplios"
            subtitle="Compran cientos o miles de empresas de una vez. Una caída aquí es el mismo conjunto de siempre a menor precio."
            items={data.broad}
            order={data.order_notice}
            news={data.news_notice}
            empty="Ningún fondo amplio de tu universo ha caído lo suficiente."
          />
          <Group
            title="Acciones sueltas"
            subtitle="Una sola empresa. Aquí la herramienta NO puede distinguir una caída pasajera de un negocio deteriorándose."
            items={data.individual}
            order={data.order_notice}
            news={data.news_notice}
            empty="Ninguna acción suelta de tu universo ha caído lo suficiente."
            careful
          />
        </>
      )}

      {data.problems.length > 0 && (
        <section className="card">
          <h2>Lo que no se pudo mirar</h2>
          <ul className="small gaps">
            {data.problems.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function Group({ title, subtitle, items, order, news, empty, careful = false }) {
  return (
    <section className={`card${careful ? ' card--careful' : ''}`}>
      <h2>
        {title} ({items.length})
      </h2>
      <p className="muted small">{subtitle}</p>
      {!items.length ? (
        <p className="muted">{empty}</p>
      ) : (
        <>
          <p className="muted small">{order}</p>
          {items.map((it) => (
            <FallenCard key={it.ticker} item={it} newsNotice={news} />
          ))}
        </>
      )}
    </section>
  )
}

function FallenCard({ item, newsNotice }) {
  const [open, setOpen] = useState(false)

  return (
    <article className="fallen">
      <header className="fallen__head">
        <div>
          <strong>{item.ticker}</strong>
          {item.name && <span className="muted"> {item.name}</span>}
          {item.held && <span className="tag tag--sm">ya la tienes</span>}
        </div>
        {/* La cifra no lleva color de «bueno» ni de «malo»: es un hecho, y
            pintarla verde insinuaría que caer es una buena noticia. */}
        <div className="fallen__dd">{item.drawdown.formatted}</div>
      </header>

      <p className="fallen__reading">{item.reading}</p>

      <ul className="risks small">
        {item.warnings.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>

      <button className="linkish" onClick={() => setOpen((v) => !v)}>
        {open ? 'Ocultar el detalle' : 'Ver las cifras y qué se dice'}
      </button>

      {open && (
        <div className="fallen__body">
          <Datum item={item.drawdown} />
          <Datum item={item.last_close} />
          <Datum item={item.high_52w} />

          <h4>Qué se dice sobre esta caída</h4>
          <p className="muted small">{newsNotice}</p>
          {!item.news.length ? (
            <p className="muted small">No se encontraron titulares recientes.</p>
          ) : (
            <ul className="news small">
              {item.news.map((n, i) => (
                <li key={i}>
                  <SafeLink url={n.url}>{n.title}</SafeLink>
                  <span className="muted"> — {n.source_name}, {n.published ?? 'sin fecha'}</span>
                </li>
              ))}
            </ul>
          )}

          <p className="small">
            <Link to="/analizar">Analizar {item.ticker} a fondo →</Link>
          </p>
        </div>
      )}
    </article>
  )
}
