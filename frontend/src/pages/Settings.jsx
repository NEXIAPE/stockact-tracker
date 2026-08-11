/** Ajustes: fuentes de datos, exportar y borrar. Tus datos son tuyos. */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorBox, Loading, Notice } from '../components/Data.jsx'
import { efectivo, elegir, preferencia } from '../tema.js'

export default function Settings() {
  const [sources, setSources] = useState(null)
  const [health, setHealth] = useState(null)
  const [acceso, setAcceso] = useState(null)
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.sources(), api.health(), api.authStatus()])
      .then(([s, h, a]) => {
        setSources(s)
        setHealth(h)
        setAcceso(a)
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
        <table className="table table--stack">
          <thead>
            <tr><th>Fuente</th><th>Qué aporta</th><th>Costo</th><th>Límites</th><th>Estado</th></tr>
          </thead>
          <tbody>
            {sources.sources.map((s) => (
              <tr key={s.name}>
                <td data-label="Fuente"><strong>{s.name}</strong></td>
                <td data-label="Qué aporta" className="small">{s.provides}</td>
                <td data-label="Costo" className="small">{s.cost}</td>
                <td data-label="Límites" className="small muted">{s.limits}</td>
                <td data-label="Estado">
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

      <ThemeSection />

      <AccessSection acceso={acceso} onError={setError} />

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

/** Claro u oscuro. Sin previsualizaciones ni animación: se aplica y ya está. */
function ThemeSection() {
  const [pref, setPref] = useState(preferencia)

  const cambiar = (p) => {
    elegir(p)
    setPref(p)
  }

  const ETIQUETAS = {
    auto: 'Automático (sigue a tu sistema)',
    claro: 'Siempre claro',
    oscuro: 'Siempre oscuro',
  }

  return (
    <section className="card">
      <h2>Apariencia</h2>
      <div className="choices">
        {Object.entries(ETIQUETAS).map(([valor, texto]) => (
          <label key={valor} className={`choice${pref === valor ? ' on' : ''}`}>
            <input
              type="radio"
              name="tema"
              checked={pref === valor}
              onChange={() => cambiar(valor)}
            />
            {texto}
          </label>
        ))}
      </div>
      <p className="muted small">
        Ahora mismo se ve en <strong>{efectivo(pref)}</strong>. Sólo cambian los colores:
        ningún dato, ningún cálculo y ninguna regla dependen de esto.
      </p>
    </section>
  )
}

/**
 * Acceso a la herramienta.
 *
 * Se pinta distinto según esté publicada o no, porque el consejo correcto es el
 * contrario en cada caso: sin contraseña en tu propio ordenador está bien, sin
 * contraseña en internet es tu cartera a la vista de cualquiera.
 */
function AccessSection({ acceso, onError }) {
  if (!acceso) return null

  if (!acceso.auth_required) {
    return (
      <section className="card">
        <h2>Acceso</h2>
        <p className="muted small">
          Esta copia funciona <strong>sin contraseña</strong>. En tu propio ordenador es lo
          normal: nadie más llega a esta dirección.
        </p>
        <Notice kind="warn">
          Si algún día la publicas en internet, ponle contraseña antes. Sin ella, cualquiera
          con el enlace vería tu cartera y podría borrarla. Está explicado en el README, en
          «Publicarla en internet».
        </Notice>
      </section>
    )
  }

  return (
    <section className="card">
      <h2>Acceso</h2>
      <p className="muted small">
        Esta copia pide contraseña. La sesión dura 12 horas y luego vuelve a pedirla.
      </p>
      <p className="small">
        Si sospechas que alguien más pudo entrar, o has perdido un dispositivo donde la
        tenías abierta, puedes invalidar todas las sesiones a la vez. Tendrás que volver a
        entrar aquí también. Tus datos no se tocan.
      </p>
      <button
        onClick={() =>
          api
            .logoutEverywhere()
            // Esta sesión es una de las que se cierran, así que la pantalla que
            // estás mirando ya no vale. Recargar devuelve al formulario de
            // acceso, y ver ese formulario es la confirmación de que funcionó.
            .then(() => window.location.reload())
            .catch(onError)
        }
      >
        Cerrar todas las sesiones
      </button>
    </section>
  )
}
