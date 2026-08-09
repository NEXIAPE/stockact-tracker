import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api, setUnauthorizedHandler } from './api.js'
import Login from './pages/Login.jsx'
import Alerts from './pages/Alerts.jsx'
import Analyze from './pages/Analyze.jsx'
import Briefing from './pages/Briefing.jsx'
import Onboarding from './pages/Onboarding.jsx'
import Portfolio from './pages/Portfolio.jsx'
import Settings from './pages/Settings.jsx'
import Watchlist from './pages/Watchlist.jsx'

export default function App() {
  const [configured, setConfigured] = useState(null)
  const [unread, setUnread] = useState(0)
  const [sesion, setSesion] = useState(null)   // null = aún comprobando

  const comprobarSesion = () =>
    api
      .authStatus()
      .then((s) => setSesion(s))
      .catch(() => setSesion({ auth_required: false, authenticated: true }))

  useEffect(() => {
    // Si la sesión caduca mientras usas la app, se vuelve al acceso.
    setUnauthorizedHandler(() => setSesion((s) => ({ ...s, authenticated: false })))
    comprobarSesion()
  }, [])

  useEffect(() => {
    if (!sesion?.authenticated) return
    api
      .getProfile()
      .then((p) => setConfigured(p.configured))
      .catch(() => setConfigured(false))
  }, [sesion?.authenticated])

  useEffect(() => {
    if (!configured || !sesion?.authenticated) return
    api
      .alerts(true)
      .then((r) => setUnread(r.alerts.length))
      .catch(() => setUnread(0))
  }, [configured, sesion?.authenticated])

  if (sesion === null) return <p className="muted center">Cargando…</p>

  if (sesion.auth_required && !sesion.authenticated) {
    return <Login onEntered={comprobarSesion} />
  }

  if (configured === null) return <p className="muted center">Cargando…</p>

  return (
    <div className="app">
      <nav className="nav">
        <span className="nav__brand">Mi inversión</span>
        <NavLink to="/">Briefing</NavLink>
        <NavLink to="/analizar">Analizar</NavLink>
        <NavLink to="/cartera">Cartera</NavLink>
        <NavLink to="/watchlist">Watchlist</NavLink>
        <NavLink to="/alertas">
          Alertas{unread > 0 && <span className="badge">{unread}</span>}
        </NavLink>
        <NavLink to="/perfil">Perfil</NavLink>
        <NavLink to="/ajustes">Ajustes</NavLink>
        {sesion.auth_required && (
          <button
            className="linkish nav__logout"
            onClick={() => api.logout().then(comprobarSesion)}
          >
            Salir
          </button>
        )}
        <span className="nav__note">solo lectura · nunca opera</span>
      </nav>

      <main>
        <Routes>
          <Route path="/" element={configured ? <Briefing /> : <Navigate to="/perfil" replace />} />
          <Route path="/analizar" element={<Analyze />} />
          <Route path="/cartera" element={<Portfolio />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/alertas" element={<Alerts />} />
          <Route path="/perfil" element={<Onboarding />} />
          <Route path="/ajustes" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="foot">
        <p>
          Herramienta personal de apoyo a la decisión. Sugiere y explica; no ejecuta órdenes ni
          se conecta a ningún bróker. No es asesoría financiera ni tributaria.
        </p>
      </footer>
    </div>
  )
}
