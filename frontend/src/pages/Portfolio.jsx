/** Mi cartera: posiciones, efectivo, diversificación y bitácora. */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Datum, DatumList, ErrorBox, Loading, Money, Notice, Pct } from '../components/Data.jsx'

const EMPTY_HOLDING = { ticker: '', shares: '', avg_cost: '', asset_type: '', notes: '' }
const EMPTY_TRADE = { ticker: '', action: 'compra', shares: '', price: '', traded_on: '', notes: '' }

export default function Portfolio() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [perf, setPerf] = useState(null)
  const [theses, setTheses] = useState({ theses: [], missing_warning: null, stale_warning: null })
  const [trades, setTrades] = useState([])
  const [holding, setHolding] = useState(EMPTY_HOLDING)
  const [trade, setTrade] = useState(EMPTY_TRADE)
  const [cash, setCash] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    Promise.all([api.getPortfolio(), api.listTrades(), api.theses()])
      .then(([p, t, th]) => {
        setData(p)
        setTrades(t.trades)
        setTheses(th)
        setCash(String(p.cash ?? 0))
      })
      .catch((err) => (err.status === 409 ? navigate('/perfil') : setError(err)))
      .finally(() => setLoading(false))

    // El rendimiento se pide aparte porque descarga el histórico del índice de
    // referencia y tarda más; no debe retrasar el resto de la pantalla.
    setPerf(null)
    api.performance().then(setPerf).catch(() => setPerf(null))
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

  if (loading) return <Loading what="Valorando tu cartera con precios reales" />
  if (!data) return <ErrorBox error={error} />

  return (
    <div className="page">
      <h1>Mi cartera</h1>
      <p className="lead">
        Aquí registras lo que YA tienes. La herramienta no se conecta a tu bróker: tú operas a
        mano en hAPI y luego lo anotas para que todo lo demás sea real.
      </p>

      <ErrorBox error={error} />
      {data.data_warning && <Notice kind="warn">{data.data_warning}</Notice>}

      <section className="card">
        <h2>Resumen</h2>
        <div className="grid">
          <Stat label="Valor total" value={<Money value={data.total_value} />} />
          <Stat label="Invertido" value={<Money value={data.invested_value} />} />
          <Stat label="Efectivo" value={<Money value={data.cash} />} />
          <Stat label="Efectivo sobre el total" value={<Pct value={data.cash_pct} />} />
          <Stat label="En acciones" value={<Pct value={data.stocks_vs_bonds.acciones} />} />
          <Stat label="En bonos" value={<Pct value={data.stocks_vs_bonds.bonos} />} />
        </div>
        <p className="muted small">Valorado el {data.as_of}.</p>
      </section>

      {data.deviations.length > 0 && (
        <section className="card">
          <h2>Cómo te va frente a tu estrategia</h2>
          {data.deviations.map((d, i) => (
            <div key={i} className="deviation">
              <span className={`tag tag--${d.severity === 'atencion' ? 'warn' : 'sm'}`}>{d.kind}</span>
              <p>{d.message}</p>
              <DatumList items={d.numbers} empty="" />
            </div>
          ))}
        </section>
      )}

      <PerformanceCard perf={perf} />

      {(theses.missing_warning || theses.stale_warning) && (
        <section className="card">
          <h2>Por qué compraste lo que tienes</h2>
          <p className="muted small">{theses.why_it_matters}</p>
          {theses.missing_warning && <Notice kind="warn">{theses.missing_warning}</Notice>}
          {theses.stale_warning && <Notice kind="info">{theses.stale_warning}</Notice>}
        </section>
      )}

      <section className="card">
        <h2>Posiciones</h2>
        {!data.positions.length ? (
          <p className="muted">Todavía no registraste ninguna posición.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Símbolo</th><th>Tipo</th><th>Participaciones</th><th>Coste medio</th>
                <th>Precio</th><th>Valor</th><th>Peso</th><th>P/G</th><th></th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((p) => (
                <tr key={p.ticker}>
                  <td>
                    <strong>{p.ticker}</strong>
                    <div className="muted small">{p.sector}</div>
                  </td>
                  <td>{p.asset_type === 'etf' ? (p.is_broad_etf ? 'ETF amplio' : 'ETF') : 'Acción'}</td>
                  <td>{p.shares}</td>
                  <td><Money value={p.avg_cost} /></td>
                  <td>
                    {p.price ? <Datum item={p.price} /> : <span className="muted">{p.price_error}</span>}
                  </td>
                  <td><Money value={p.market_value} /></td>
                  <td><Pct value={p.weight_pct} /></td>
                  <td className={p.unrealized_gain >= 0 ? 'pos' : 'neg'}>
                    <Money value={p.unrealized_gain} /> (<Pct value={p.unrealized_gain_pct} />)
                  </td>
                  <td>
                    <button onClick={() => act(() => api.deleteHolding(p.ticker))}>Quitar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data.positions.length > 0 && (
          <div className="theses">
            <h3>Tu tesis de cada posición</h3>
            <p className="muted small">
              Por qué la compraste y qué te haría cambiar de idea. Es lo único que permite
              opinar sobre vender sin apoyarse sólo en el precio.
            </p>
            {data.positions.map((p) => (
              <ThesisEditor
                key={p.ticker}
                ticker={p.ticker}
                current={theses.theses.find((t) => t.ticker === p.ticker)}
                onSaved={load}
              />
            ))}
          </div>
        )}

        <h3>Añadir o actualizar una posición</h3>
        <form
          className="row wrap"
          onSubmit={(e) => {
            e.preventDefault()
            act(() =>
              api.saveHolding({
                ticker: holding.ticker.toUpperCase(),
                shares: Number(holding.shares),
                avg_cost: Number(holding.avg_cost),
                asset_type: holding.asset_type || null,
                notes: holding.notes,
              }),
            ).then(() => setHolding(EMPTY_HOLDING))
          }}
        >
          <input required placeholder="Símbolo" value={holding.ticker}
            onChange={(e) => setHolding({ ...holding, ticker: e.target.value.toUpperCase() })} />
          <input required type="number" step="any" min="0" placeholder="Participaciones"
            value={holding.shares} onChange={(e) => setHolding({ ...holding, shares: e.target.value })} />
          <input required type="number" step="any" min="0" placeholder="Coste medio (USD)"
            value={holding.avg_cost} onChange={(e) => setHolding({ ...holding, avg_cost: e.target.value })} />
          <select value={holding.asset_type}
            onChange={(e) => setHolding({ ...holding, asset_type: e.target.value })}>
            <option value="">Detectar tipo</option>
            <option value="etf">ETF</option>
            <option value="accion">Acción</option>
          </select>
          <button className="primary" type="submit">Guardar</button>
        </form>
      </section>

      <section className="card">
        <h2>Efectivo disponible</h2>
        <form className="row" onSubmit={(e) => { e.preventDefault(); act(() => api.setCash(Number(cash))) }}>
          <input type="number" step="any" min="0" value={cash} onChange={(e) => setCash(e.target.value)} />
          <button type="submit">Actualizar</button>
        </form>
        <p className="muted small">
          Actualizado el {data.cash_updated ?? 'nunca'}. Sirve para calcular tamaños de posición
          realistas: sin saber tu efectivo, cualquier sugerencia de importe sería inventada.
        </p>
      </section>

      <section className="card">
        <h2>Reparto por sector</h2>
        {!Object.keys(data.sector_weights).length ? (
          <p className="muted">Sin datos todavía.</p>
        ) : (
          <ul className="bars">
            {Object.entries(data.sector_weights)
              .sort((a, b) => b[1] - a[1])
              .map(([sector, pct]) => (
                <li key={sector}>
                  <span className="bars__label">{sector}</span>
                  <span className="bars__track">
                    <span className="bars__fill" style={{ width: `${Math.min(100, pct)}%` }} />
                  </span>
                  <span className="bars__val"><Pct value={pct} /></span>
                </li>
              ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Bitácora de operaciones</h2>
        <p className="muted small">
          Registro de lo que tú ya ejecutaste en tu bróker. Esto no envía ninguna orden.
        </p>
        <form
          className="row wrap"
          onSubmit={(e) => {
            e.preventDefault()
            act(() =>
              api.addTrade({
                ticker: trade.ticker.toUpperCase(),
                action: trade.action,
                shares: Number(trade.shares),
                price: Number(trade.price),
                traded_on: trade.traded_on,
                notes: trade.notes,
              }),
            ).then(() => setTrade(EMPTY_TRADE))
          }}
        >
          <input required placeholder="Símbolo" value={trade.ticker}
            onChange={(e) => setTrade({ ...trade, ticker: e.target.value.toUpperCase() })} />
          <select value={trade.action} onChange={(e) => setTrade({ ...trade, action: e.target.value })}>
            <option value="compra">Compra</option>
            <option value="venta">Venta</option>
          </select>
          <input required type="number" step="any" min="0" placeholder="Participaciones"
            value={trade.shares} onChange={(e) => setTrade({ ...trade, shares: e.target.value })} />
          <input required type="number" step="any" min="0" placeholder="Precio (USD)"
            value={trade.price} onChange={(e) => setTrade({ ...trade, price: e.target.value })} />
          <input required type="date" value={trade.traded_on}
            onChange={(e) => setTrade({ ...trade, traded_on: e.target.value })} />
          <button type="submit">Anotar</button>
        </form>

        {trades.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>Fecha</th><th>Símbolo</th><th>Operación</th><th>Participaciones</th><th>Precio</th><th></th></tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id}>
                  <td>{t.traded_on}</td>
                  <td>{t.ticker}</td>
                  <td>{t.action}</td>
                  <td>{t.shares}</td>
                  <td><Money value={t.price} /></td>
                  <td><button onClick={() => act(() => api.deleteTrade(t.id))}>Borrar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
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

function PerformanceCard({ perf }) {
  if (!perf) {
    return (
      <section className="card">
        <h2>Cómo te va de verdad</h2>
        <p className="muted">Calculando y descargando el histórico del índice de referencia…</p>
      </section>
    )
  }

  const tuyo = perf.gain_pct
  const indice = perf.benchmark_gain_pct
  const escala = Math.max(Math.abs(tuyo ?? 0), Math.abs(indice ?? 0), 1)

  return (
    <section className="card">
      <h2>Cómo te va de verdad</h2>
      <div className="perf">
        <p className="perf__verdict">{perf.verdict}</p>

        {tuyo !== null && indice !== null && (
          <div className="perf__bars">
            <div className="perf__bar">
              <span>Tu cartera</span>
              <span className="perf__track">
                <span className="perf__fill" style={{ width: `${Math.min(100, (Math.abs(tuyo) / escala) * 100)}%` }} />
              </span>
              <span className={tuyo >= 0 ? 'pos' : 'neg'}><Pct value={tuyo} /></span>
            </div>
            <div className="perf__bar">
              <span>Sólo {perf.benchmark_ticker}</span>
              <span className="perf__track">
                <span className="perf__fill perf__fill--bench"
                      style={{ width: `${Math.min(100, (Math.abs(indice) / escala) * 100)}%` }} />
              </span>
              <span className={indice >= 0 ? 'pos' : 'neg'}><Pct value={indice} /></span>
            </div>
          </div>
        )}

        <DatumList items={perf.data} empty="" />

        <p className="muted small">{perf.method}</p>
        {perf.notes.length > 0 && (
          <ul className="small gaps">
            {perf.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function ThesisEditor({ ticker, current, onSaved }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    thesis: current?.text ?? '',
    invalidation: current?.invalidation ?? '',
  })
  const [saving, setSaving] = useState(false)

  const falta = !current?.exists

  return (
    <div className={falta ? 'thesis-edit thesis-edit--missing' : 'thesis-edit'}>
      <div className="row wrap">
        <strong>{ticker}</strong>
        {falta ? (
          <span className="tag tag--warn">sin tesis</span>
        ) : (
          <span className="muted small">
            revisada {current.reviewed_at ?? 'nunca'}
            {current.is_stale && ' · conviene releerla'}
          </span>
        )}
        <button className="linkish" onClick={() => setOpen((v) => !v)}>
          {open ? 'cancelar' : falta ? 'anotar por qué la compraste' : 'revisar'}
        </button>
      </div>

      {!open && current?.exists && <p className="small thesis__text">{current.text}</p>}

      {open && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setSaving(true)
            api
              .saveThesis(ticker, { ...form, mark_reviewed: true })
              .then(() => {
                setOpen(false)
                onSaved()
              })
              .finally(() => setSaving(false))
          }}
        >
          <label className="field__label">¿Por qué compraste {ticker}?</label>
          <textarea
            rows={2} required value={form.thesis}
            placeholder="p. ej. quiero exposición a todo el mercado sin elegir empresas"
            onChange={(e) => setForm({ ...form, thesis: e.target.value })}
          />
          <label className="field__label">¿Qué te haría dejar de creerlo?</label>
          <textarea
            rows={2} value={form.invalidation}
            placeholder="p. ej. si apareciera un fondo equivalente mucho más barato"
            onChange={(e) => setForm({ ...form, invalidation: e.target.value })}
          />
          <button className="primary" type="submit" disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar y marcar como revisada'}
          </button>
        </form>
      )}
    </div>
  )
}
