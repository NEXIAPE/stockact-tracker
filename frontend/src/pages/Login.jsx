/**
 * Pantalla de acceso. Sólo aparece cuando la instancia tiene contraseña.
 *
 * Deliberadamente escueta: no dice si la instancia tiene datos, ni de quién es,
 * ni cuántos intentos quedan. Todo eso sería información gratis para quien esté
 * probando desde fuera.
 */

import { useState } from 'react'
import { api } from '../api.js'

export default function Login({ onEntered }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [espera, setEspera] = useState(0)
  const [enviando, setEnviando] = useState(false)

  const entrar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      await api.login(password)
      setPassword('')
      onEntered()
    } catch (err) {
      const d = err.detail
      setError(d?.message || 'No se pudo entrar.')
      setEspera(d?.retry_after_seconds ?? 0)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login">
      <form className="login__card" onSubmit={entrar}>
        <h1>Mi inversión</h1>
        <p className="muted">Esta herramienta está protegida con contraseña.</p>

        <label className="field__label" htmlFor="password">Contraseña</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={enviando || espera > 0}
        />

        <button className="primary" type="submit" disabled={enviando || espera > 0 || !password}>
          {enviando ? 'Comprobando…' : 'Entrar'}
        </button>

        {error && (
          <p className="login__error">
            {error}
            {espera > 0 && ' Este bloqueo existe para que nadie pueda ir probando contraseñas.'}
          </p>
        )}

        <p className="login__foot">
          Solo lectura: esta herramienta nunca envía órdenes a un bróker. No es asesoría
          financiera ni tributaria.
        </p>
      </form>
    </div>
  )
}
