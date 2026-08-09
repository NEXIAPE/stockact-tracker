/** Watchlist: lo que sigues, tus criterios de aviso y datos que registras tú. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorBox, Loading, Notice, SafeLink } from '../components/Data.jsx'

const EMPTY = { ticker: '', reason: '', target_buy_price: '', max_drawdown_pct: '', asset_type: '' }

export default function Watchlist() {
  const [items, setItems] = useState([])
  const [catalog, setCatalog] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    Promise.all([api.getWatchlist(), api.etfCatalog()])
      .then(([w, c]) => {
        setItems(w.items)
        setCatalog(c.etfs)
      })
      .catch(setError)
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const act = async (fn) => {
    setError(null)
    try {
      await fn()
      load()
    } catch (err) {
      setError(err)
    }
  }

  if (loading) return <Loading what="Cargando tu watchlist" />

  return (
    <div className="page">
      <h1>Watchlist</h1>
      <p className="lead">
        Los símbolos que quieres seguir. Puedes fijar criterios propios y la herramienta te
        avisará cuando se cumplan — para que mires, no para que compres.
      </p>

      <ErrorBox error={error} />

      <section className="card">
        <h2>Añadir un símbolo</h2>
        <form
          className="row wrap"
          onSubmit={(e) => {
            e.preventDefault()
            act(() =>
              api.addWatch({
                ticker: form.ticker.toUpperCase(),
                reason: form.reason,
                asset_type: form.asset_type || null,
                target_buy_price: form.target_buy_price ? Number(form.target_buy_price) : null,
                max_drawdown_pct: form.max_drawdown_pct ? Number(form.max_drawdown_pct) : null,
              }),
            ).then(() => setForm(EMPTY))
          }}
        >
          <input required placeholder="Símbolo" value={form.ticker}
            onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })} />
          <input placeholder="¿Por qué lo sigues?" value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          <input type="number" step="any" min="0" placeholder="Avísame si baja de (USD)"
            value={form.target_buy_price}
            onChange={(e) => setForm({ ...form, target_buy_price: e.target.value })} />
          <input type="number" step="any" min="1" max="99" placeholder="Avísame si cae % desde máximos"
            value={form.max_drawdown_pct}
            onChange={(e) => setForm({ ...form, max_drawdown_pct: e.target.value })} />
          <button className="primary" type="submit">Añadir</button>
        </form>
      </section>

      <section className="card">
        <h2>Sigues {items.length} símbolo(s)</h2>
        {!items.length ? (
          <p className="muted">Todavía no sigues nada.</p>
        ) : (
          items.map((it) => <WatchRow key={it.ticker} item={it} onChange={act} />)
        )}
      </section>

      <section className="card">
        <h2>Catálogo de ETFs de referencia</h2>
        <Notice kind="info">
          Este catálogo no trae comisiones ni cifras. Los ratios de gastos cambian y
          escribirlos a mano en el código sería inventar datos. Léelos en la ficha oficial y
          regístralos: entonces aparecerán citados con la fecha en que los leíste.
        </Notice>
        <table className="table table--stack">
          <thead>
            <tr><th>Símbolo</th><th>Nombre</th><th>Qué te da</th><th>Tipo</th><th>Ficha oficial</th><th></th></tr>
          </thead>
          <tbody>
            {catalog.map((e) => (
              <tr key={e.ticker}>
                <td data-label="Símbolo"><strong>{e.ticker}</strong></td>
                <td data-label="Nombre">{e.name}<div className="muted small">{e.issuer}</div></td>
                <td data-label="Qué te da" className="small">{e.exposure}</td>
                <td data-label="Tipo">
                  <span className={`tag tag--${e.is_broad ? 'ok' : 'warn'}`}>
                    {e.is_broad ? 'amplio' : e.breadth}
                  </span>
                </td>
                <td data-label="Ficha oficial"><SafeLink url={e.factsheet_url}>abrir</SafeLink></td>
                <td data-label="">
                  <button onClick={() => act(() => api.addWatch({ ticker: e.ticker, asset_type: 'etf' }))}>
                    Seguir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

function WatchRow({ item, onChange }) {
  const [fact, setFact] = useState({ value: '', as_of: '', source_url: item.etf_info?.factsheet_url ?? '' })
  const [open, setOpen] = useState(false)

  return (
    <div className="watch">
      <div className="watch__head">
        <div>
          <strong>{item.ticker}</strong>{' '}
          <span className="tag tag--sm">{item.asset_type === 'etf' ? 'ETF' : 'Acción'}</span>
          {item.reason && <p className="muted small">{item.reason}</p>}
        </div>
        <div className="row">
          <Link to="/analizar">Analizar</Link>
          <button onClick={() => onChange(() => api.removeWatch(item.ticker))}>Quitar</button>
        </div>
      </div>

      <p className="small muted">
        {item.target_buy_price
          ? `Te aviso si el cierre baja de US$ ${item.target_buy_price}. `
          : 'Sin precio de referencia. '}
        {item.max_drawdown_pct
          ? `Te aviso si cae más de ${item.max_drawdown_pct} % desde su máximo de 52 semanas.`
          : 'Sin umbral de caída.'}
      </p>

      {item.registered_facts.length > 0 && (
        <ul className="small">
          {item.registered_facts.map((f) => (
            <li key={f.key}>
              {f.key}: <strong>{f.value} {f.unit}</strong> — {f.source_label}, leído el {f.as_of}
              {f.source_url && (
                <>
                  {' '}(<SafeLink url={f.source_url}>fuente</SafeLink>)
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <button className="linkish" onClick={() => setOpen((v) => !v)}>
        {open ? 'Cancelar' : 'Registrar el ratio de gastos que leíste en la ficha oficial'}
      </button>

      {open && (
        <form
          className="row wrap"
          onSubmit={(e) => {
            e.preventDefault()
            onChange(() =>
              api.registerFact(item.ticker, {
                key: 'expense_ratio',
                value: Number(fact.value),
                unit: '%',
                source_label: 'Ficha oficial del emisor',
                source_url: fact.source_url,
                as_of: fact.as_of,
              }),
            ).then(() => setOpen(false))
          }}
        >
          <input required type="number" step="any" min="0" placeholder="Ratio de gastos (%)"
            value={fact.value} onChange={(e) => setFact({ ...fact, value: e.target.value })} />
          <input required type="date" title="Fecha en que lo leíste"
            value={fact.as_of} onChange={(e) => setFact({ ...fact, as_of: e.target.value })} />
          <input placeholder="URL de la ficha" value={fact.source_url}
            onChange={(e) => setFact({ ...fact, source_url: e.target.value })} />
          <button type="submit">Guardar dato citado</button>
        </form>
      )}
    </div>
  )
}
