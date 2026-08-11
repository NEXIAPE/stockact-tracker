/**
 * Onboarding: define tu perfil y ve la estrategia que se deriva de él.
 *
 * Cada pregunta explica POR QUÉ se hace. La estrategia resultante muestra el
 * porqué de cada regla, para que puedas discutirla en vez de aceptarla a ciegas.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { ErrorBox, Loading, Notice, Pct } from '../components/Data.jsx'

const EMPTY = {
  initial_capital: '',
  monthly_contribution: '',
  risk_tolerance: 'moderado',
  horizon_years: '',
  goals: [],
  experience: 'principiante',
  emergency_fund_ok: false,
  notes: '',
}

export default function Onboarding() {
  const navigate = useNavigate()
  const [steps, setSteps] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [goalDraft, setGoalDraft] = useState('')
  const [saved, setSaved] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.onboardingSteps(), api.getProfile()])
      .then(([s, p]) => {
        setSteps(s.steps)
        if (p.configured) {
          setForm({ ...EMPTY, ...p.profile, goals: p.profile.goals ?? [] })
          setSaved(p.profile)
        }
      })
      .catch(setError)
      .finally(() => setLoading(false))
  }, [])

  const set = (field, value) => setForm((f) => ({ ...f, [field]: value }))

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    try {
      const payload = {
        ...form,
        initial_capital: Number(form.initial_capital || 0),
        monthly_contribution: Number(form.monthly_contribution || 0),
        horizon_years: Number(form.horizon_years || 1),
      }
      const res = await api.saveProfile(payload)
      setSaved(res.profile)
    } catch (err) {
      setError(err)
    }
  }

  if (loading) return <Loading what="Preparando el onboarding" />

  const help = (id) => steps.find((s) => s.id === id)?.help ?? ''

  return (
    <div className="page">
      <h1>Tu perfil</h1>
      <p className="lead">
        Con esto personalizo todo lo demás: qué ideas te propongo, de qué tamaño y cuándo te
        aviso. No hay respuestas correctas; hay respuestas tuyas.
      </p>

      <ErrorBox error={error} />

      <form onSubmit={submit} className="form">
        <Field label="¿Con cuánto empiezas? (USD)" help={help('capital')}>
          <input
            type="number" min="0" step="any" required
            value={form.initial_capital}
            onChange={(e) => set('initial_capital', e.target.value)}
          />
        </Field>

        <Field label="¿Cuánto puedes aportar cada mes? (USD)" help={help('aporte')}>
          <input
            type="number" min="0" step="any"
            value={form.monthly_contribution}
            onChange={(e) => set('monthly_contribution', e.target.value)}
          />
        </Field>

        <Field label="¿Cuánto riesgo aguantas?" help={help('riesgo')}>
          <div className="choices">
            {steps.find((s) => s.id === 'riesgo')?.options?.map((o) => (
              <label key={o.value} className={form.risk_tolerance === o.value ? 'choice on' : 'choice'}>
                <input
                  type="radio" name="risk" value={o.value}
                  checked={form.risk_tolerance === o.value}
                  onChange={() => set('risk_tolerance', o.value)}
                />
                <strong>{o.label}</strong>
                <span className="muted small">{o.help}</span>
              </label>
            ))}
          </div>
        </Field>

        <Field label="¿A cuántos años inviertes?" help={help('horizonte')}>
          <input
            type="number" min="1" max="60" required
            value={form.horizon_years}
            onChange={(e) => set('horizon_years', e.target.value)}
          />
        </Field>

        <Field label="¿Para qué es este dinero?" help={help('objetivos')}>
          <div className="row">
            <input
              type="text" placeholder="p. ej. jubilación, casa propia"
              value={goalDraft}
              onChange={(e) => setGoalDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  if (goalDraft.trim()) {
                    set('goals', [...form.goals, goalDraft.trim()])
                    setGoalDraft('')
                  }
                }
              }}
            />
            <button
              type="button"
              onClick={() => {
                if (goalDraft.trim()) {
                  set('goals', [...form.goals, goalDraft.trim()])
                  setGoalDraft('')
                }
              }}
            >
              Añadir
            </button>
          </div>
          <ul className="chips">
            {form.goals.map((g, i) => (
              <li key={i}>
                {g}
                <button type="button" onClick={() => set('goals', form.goals.filter((_, j) => j !== i))}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        </Field>

        <Field label="¿Tienes un fondo de emergencia?" help={help('emergencia')}>
          <label className="inline">
            <input
              type="checkbox"
              checked={form.emergency_fund_ok}
              onChange={(e) => set('emergency_fund_ok', e.target.checked)}
            />
            Sí, tengo unos meses de gastos guardados aparte
          </label>
        </Field>

        <Field label="¿Cuánta experiencia tienes?" help={help('experiencia')}>
          <select value={form.experience} onChange={(e) => set('experience', e.target.value)}>
            {steps.find((s) => s.id === 'experiencia')?.options?.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </Field>

        <button className="primary" type="submit">Guardar perfil</button>
      </form>

      {saved && <StrategyView strategy={saved.strategy} onContinue={() => navigate('/')} />}
    </div>
  )
}

function Field({ label, help, children }) {
  return (
    <div className="field">
      <label className="field__label">{label}</label>
      {help && <p className="field__help">{help}</p>}
      {children}
    </div>
  )
}

function StrategyView({ strategy, onContinue }) {
  return (
    <section className="card">
      <h2>Tu estrategia mínima</h2>
      <p className="muted">
        Esto no sale de ninguna fórmula secreta: sale de lo que acabas de responder.
      </p>

      <div className="grid">
        <Stat label="En acciones" value={<Pct value={strategy.target_stocks_pct} />} />
        <Stat label="En bonos" value={<Pct value={strategy.target_bonds_pct} />} />
        <Stat label="Máximo por posición" value={<Pct value={strategy.max_position_pct} />} />
        <Stat label="Máximo en una sola acción" value={<Pct value={strategy.max_single_stock_pct} />} />
        <Stat label="Máximo por sector" value={<Pct value={strategy.max_sector_pct} />} />
        <Stat label="Efectivo objetivo" value={
          <>
            <Pct value={strategy.min_cash_pct} /> – <Pct value={strategy.max_cash_pct} />
          </>
        } />
      </div>

      <Notice kind="info" title="Núcleo y satélite">
        {strategy.core_satellite_note}
      </Notice>

      <h3>Por qué salió así</h3>
      <ul>
        {strategy.rationale.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <button className="primary" onClick={onContinue}>Ir a mi briefing</button>
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
