/**
 * Tarjeta de recomendación.
 *
 * Defensa en profundidad: aunque el backend ya bloquea cualquier recomendación
 * sin riesgos o sin contra-argumento, este componente vuelve a comprobarlo y se
 * niega a pintarla si faltan. Dos candados independientes para la misma regla.
 */

import { useState } from 'react'
import { Datum, DatumList, Money, Notice } from './Data.jsx'

const ACTION_STYLE = {
  comprar: 'act act--buy',
  mantener: 'act act--hold',
  evitar: 'act act--avoid',
  vender: 'act act--sell',
}

function incomplete(rec) {
  const problems = []
  if (!rec?.risks?.length) problems.push('no trae riesgos')
  if (!rec?.counter_argument?.trim()) problems.push('no trae contra-argumento')
  if (!rec?.confidence?.basis?.length) problems.push('no dice en qué se basa su confianza')
  return problems
}

export function RecommendationCard({ rec, compact = false }) {
  const [open, setOpen] = useState(!compact)
  const problems = incomplete(rec)

  if (problems.length) {
    return (
      <Notice kind="error" title="Recomendación bloqueada">
        Esta recomendación {problems.join(' y ')}. Una recomendación incompleta es un defecto
        del programa, así que no se muestra. No es algo que hayas hecho mal.
      </Notice>
    )
  }

  return (
    <article className="rec">
      <header className="rec__head">
        <div>
          <h3>
            {rec.ticker} <span className="muted">{rec.name}</span>
          </h3>
          <span className="tag">{rec.asset_type === 'etf' ? 'ETF' : 'Acción'}</span>
        </div>
        <div className={ACTION_STYLE[rec.action] ?? 'act'}>{rec.action_label}</div>
      </header>

      {rec.why_surfaced && <p className="rec__why">{rec.why_surfaced}</p>}

      <p className="rec__thesis">{rec.thesis}</p>

      <SizingBlock sizing={rec.suggested_position} alternative={rec.sizing_is_alternative} />

      {rec.beginner_warnings?.length > 0 && (
        <Notice kind="warn" title="Antes de seguir">
          <ul>
            {rec.beginner_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </Notice>
      )}

      <button className="linkish" onClick={() => setOpen((v) => !v)}>
        {open ? 'Ocultar el detalle' : 'Ver evidencia, riesgos y contra-argumento'}
      </button>

      {open && (
        <div className="rec__body">
          <Section title="Evidencia a favor y en contra">
            <p className="muted small">
              Cada cifra viene de una fuente real, con su fecha. Lo que no se pudo obtener
              aparece marcado como no disponible.
            </p>
            {rec.evidence.map((ev, i) => (
              <div className="evidence" key={i}>
                <p className="evidence__claim">
                  <span className="tag tag--sm">{ev.kind}</span> {ev.claim}
                </p>
                <DatumList items={ev.data} empty="Sin cifras asociadas a esta observación." />
              </div>
            ))}
          </Section>

          <Section title="Riesgos concretos">
            <ul className="risks">
              {rec.risks.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </Section>

          <Section title="El argumento más fuerte en contra de esta idea">
            <p className="counter">{rec.counter_argument}</p>
          </Section>

          <Section title="Cómo encaja con tu cartera y tu estrategia">
            <p>{rec.portfolio_fit}</p>
            <DatumList items={rec.portfolio_fit_data} empty="" />
          </Section>

          <Section title={`Confianza: ${rec.confidence.level}`}>
            <p className="small muted">En qué se basa:</p>
            <ul className="small">
              {rec.confidence.basis.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            {rec.confidence.data_gaps?.length > 0 && (
              <>
                <p className="small muted">Qué le falta o es incierto:</p>
                <ul className="small gaps">
                  {rec.confidence.data_gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              </>
            )}
          </Section>

          <Section title="Cómo se llegó a esta idea">
            <table className="breakdown">
              <tbody>
                {rec.score_breakdown.map((b, i) => (
                  <tr key={i}>
                    <td className="breakdown__factor">{b.factor}</td>
                    <td className={b.points >= 0 ? 'pos' : 'neg'}>
                      {b.points > 0 ? '+' : ''}
                      {b.points}
                    </td>
                    <td className="muted small">{b.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <NewsBlock news={rec.news} notice={rec.notices.news_are_interpretation} />
          <SentimentBlock sentiment={rec.sentiment} />
          <ContextBlock signals={rec.context_signals} />

          <div className="disclaimers">
            <p>{rec.notices.read_only}</p>
            <p>{rec.notices.not_advice}</p>
          </div>
        </div>
      )}
    </article>
  )
}

function Section({ title, children }) {
  return (
    <section className="rec__section">
      <h4>{title}</h4>
      {children}
    </section>
  )
}

function SizingBlock({ sizing, alternative = false }) {
  if (!sizing?.applies) {
    return <p className="muted small">{sizing?.explanation}</p>
  }
  return (
    <div className="sizing">
      <div className="sizing__figure">
        <span className="sizing__label">
          Tamaño sugerido{alternative && ' (alternativa: no se suma a las otras ideas)'}
        </span>
        <strong>
          <Money value={sizing.amount_usd} />
        </strong>
        {sizing.pct_of_portfolio !== null && (
          <span className="muted"> · {sizing.pct_of_portfolio} % de tu cartera</span>
        )}
        {sizing.approx_shares > 0 && (
          <span className="muted"> · ≈ {sizing.approx_shares} participaciones</span>
        )}
      </div>
      <p className="small">{sizing.explanation}</p>
      <DatumList items={sizing.data} empty="" />
    </div>
  )
}

function NewsBlock({ news, notice }) {
  return (
    <Section title="Noticias recientes">
      <p className="muted small">{notice}</p>
      {!news?.length ? (
        <p className="muted">No se encontraron titulares recientes para este símbolo.</p>
      ) : (
        <ul className="news">
          {news.map((n, i) => (
            <li key={i}>
              <a href={n.url} target="_blank" rel="noreferrer">
                {n.title}
              </a>
              <span className="muted small">
                {' '}
                — {n.source_name}, {n.published ?? 'sin fecha'}
                {n.kind === 'presentacion_oficial' ? ' · documento oficial' : ' · interpretación'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function SentimentBlock({ sentiment }) {
  return (
    <Section title="Sentimiento de mercado">
      {!sentiment ? (
        <p className="muted">
          No hay dato de sentimiento en las fuentes gratuitas que usa esta herramienta. Este
          bloque queda vacío a propósito: rellenarlo con una estimación inventada sería peor
          que dejarlo en blanco.
        </p>
      ) : (
        <>
          <p className="small">{sentiment.note}</p>
          <Datum item={sentiment.beta} />
        </>
      )}
    </Section>
  )
}

function ContextBlock({ signals }) {
  if (!signals?.length) return null
  return (
    <Section title="Contexto adicional (sin peso en la idea)">
      {signals.map((s, i) => (
        <div key={i} className="context">
          <p>
            <strong>{s.title}</strong>
          </p>
          <p className="small">
            Compras divulgadas: {s.purchases} · ventas: {s.sales} · más reciente:{' '}
            {s.most_recent_transaction ?? 'sin fecha'} · fuente: {s.source_name}
          </p>
          <p className="muted small">{s.caveat}</p>
        </div>
      ))}
    </Section>
  )
}
