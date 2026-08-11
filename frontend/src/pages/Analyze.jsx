/** Análisis bajo demanda: «¿debería comprar/vender X?». */

import { useState } from 'react'
import { api } from '../api.js'
import { ErrorBox, Loading, Notice } from '../components/Data.jsx'
import { RecommendationCard } from '../components/Recommendation.jsx'

export default function Analyze() {
  const [ticker, setTicker] = useState('')
  const [assetType, setAssetType] = useState('')
  const [rec, setRec] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const run = async (e) => {
    e.preventDefault()
    if (!ticker.trim()) return
    setLoading(true)
    setError(null)
    setRec(null)
    try {
      setRec(await api.analyze(ticker.trim().toUpperCase(), assetType || undefined))
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1>¿Debería comprar o vender…?</h1>
      <p className="lead">
        Escribe un símbolo de EE. UU. y te doy una lectura completa: la idea, por qué, con
        qué números reales, qué riesgos tiene y por qué podría estar equivocada.
      </p>

      <form className="row" onSubmit={run}>
        <input
          type="text"
          placeholder="VOO, AAPL, VXUS…"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          maxLength={12}
        />
        <select value={assetType} onChange={(e) => setAssetType(e.target.value)}>
          <option value="">Detectar tipo</option>
          <option value="etf">Es un ETF</option>
          <option value="accion">Es una acción</option>
        </select>
        <button className="primary" type="submit" disabled={loading}>
          Analizar
        </button>
      </form>

      {loading && <Loading what="Consultando precios, fundamentales y noticias" />}
      <ErrorBox error={error} />

      {error?.detail?.error === 'sin_datos_suficientes' && (
        <Notice kind="info" title="Por qué no opino">
          Sin datos de precio no hay análisis posible. Prefiero decírtelo a rellenar el hueco
          con una estimación que parecería un dato real.
        </Notice>
      )}

      {rec && <RecommendationCard rec={rec} />}
    </div>
  )
}
