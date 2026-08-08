/** Ajustes: fuentes de datos, exportar y borrar. Tus datos son tuyos. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorBox, Loading, Notice } from '../components/Data.jsx'

export default function Settings() {
  const [sources, setSources] = useState(null)
  const [health, setHealth] = useState(null)
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.sources(), api.health()])
      .then(([s, h]) => {
        setSources(s)
        setHealth(h)
      })
      .catch(setError)
  }, [])

  if (error) return <ErrorBox error={error} />
  if (!sources) return <Loading what="Cargando ajustes" />

  return (
    <div className="page">
      <h1>Ajustes y tus datos</h1>

      <ErrorBox error={error} />
      {message && <Notice kind="ok">{message}</Notice>}

      <section className="card">
        <h2>Qué es y qué no es esta herramienta</h2>
        <Notice kind="info" title="Solo lectura">{sources.read_only_notice}</Notice>
        <Notice kind="warn" title="No es asesoría">{sources.not_advice_notice}</Notice>
        {health && (
          <p className="small muted">
            Conexión con bróker: <strong>ninguna</strong>. Finnhub configurado:{' '}
            <strong>{health.finnhub_configured ? 'sí' : 'no'}</strong>.
          </p>
        )}
      </section>

      <section className="card">
        <h2>Fuentes de datos</h2>
        <table className="table">
          <thead>
            <tr><th>Fuente</th><th>Qué aporta</th><th>Costo</th><th>Límites</th><th>Estado</th></tr>
          </thead>
          <tbody>
            {sources.sources.map((s) => (
              <tr key={s.name}>
                <td><strong>{s.name}</strong></td>
                <td className="small">{s.provides}</td>
                <td className="small">{s.cost}</td>
                <td className="small muted">{s.limits}</td>
                <td>
                  <span className={`tag tag--${s.enabled ? 'ok' : 'warn'}`}>
                    {s.enabled ? 'activa' : 'inactiva'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small">
          La herramienta se identifica ante las fuentes como <code>{sources.contact_user_agent}</code>.
          Cámbialo con la variable de entorno <code>INVEST_CONTACT</code>.
        </p>
      </section>

      <section className="card">
        <h2>Lo que la herramienta NO sabe (a propósito)</h2>
        <ul>
          {sources.missing_on_purpose.map((m, i) => (
            <li key={i}>
              <strong>{m.what}.</strong> {m.why}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Tu perfil</h2>
        <p className="muted small">
          Cambiar tu perfil recalcula la estrategia y, con ella, todas las ideas y avisos.
        </p>
        <Link to="/perfil">Editar mi perfil y estrategia →</Link>
      </section>

      <section className="card">
        <h2>Tus datos</h2>
        <p className="muted small">
          Un solo usuario, un solo archivo local. Puedes llevártelo todo o borrarlo todo.
        </p>
        <div className="row">
          <a className="button" href={api.exportUrl}>Exportar todo (JSON)</a>
          <button
            onClick={() =>
              api.clearCache().then((r) => setMessage(`Caché vaciada (${r.files_removed} archivos).`))
            }
          >
            Vaciar caché de fuentes
          </button>
        </div>
      </section>

      <section className="card danger">
        <h2>Borrar todo</h2>
        <p>
          Elimina tu perfil, cartera, watchlist, alertas y bitácora. No se puede deshacer.
          Exporta antes si quieres conservar algo.
        </p>
        <div className="row">
          <input placeholder="Escribe BORRAR" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          <button
            className="danger"
            disabled={confirm !== 'BORRAR'}
            onClick={() =>
              api
                .wipe()
                .then(() => {
                  setMessage('Todos tus datos han sido borrados.')
                  setConfirm('')
                })
                .catch(setError)
            }
          >
            Borrar definitivamente
          </button>
        </div>
      </section>
    </div>
  )
}
