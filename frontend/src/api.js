// Cliente de la API local. Sólo habla con el backend en tu máquina.
// El frontend nunca contacta directamente con fuentes de datos ni, por
// supuesto, con ningún bróker.

const BASE = '/api'

// Quien se suscriba aquí se entera cuando la sesión caduca, para volver al
// formulario de acceso en vez de dejar la pantalla llena de errores.
let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',   // la cookie de sesión viaja, y sólo al propio origen
    ...options,
  })

  if (res.status === 401 && !path.startsWith('/auth/')) {
    onUnauthorized()
  }

  let body = null
  try {
    body = await res.json()
  } catch {
    body = null
  }

  if (!res.ok) {
    const detail = body?.detail ?? body
    const error = new Error(
      detail?.message || detail?.error || `Error ${res.status} en ${path}`,
    )
    error.status = res.status
    error.detail = detail
    throw error
  }
  return body
}

const get = (p) => request(p)
const post = (p, body) => request(p, { method: 'POST', body: JSON.stringify(body ?? {}) })
const put = (p, body) => request(p, { method: 'PUT', body: JSON.stringify(body) })
const del = (p) => request(p, { method: 'DELETE' })

export const api = {
  health: () => get('/health'),

  authStatus: () => get('/auth/status'),
  login: (password) => post('/auth/login', { password }),
  logout: () => post('/auth/logout'),
  logoutEverywhere: () => post('/auth/logout-all'),

  onboardingSteps: () => get('/profile/onboarding'),
  getProfile: () => get('/profile'),
  saveProfile: (p) => post('/profile', p),

  getPortfolio: () => get('/portfolio'),
  // Solo lo guardado, sin tocar la red: sirve para pintar la pantalla ya.
  getPortfolioLocal: () => get('/portfolio?with_prices=false'),
  saveHolding: (h) => put('/portfolio/holdings', h),
  deleteHolding: (t) => del(`/portfolio/holdings/${encodeURIComponent(t)}`),
  setCash: (amount) => put('/portfolio/cash', { amount }),
  listTrades: () => get('/portfolio/trades'),
  performance: (benchmark) => get(`/portfolio/performance${benchmark ? `?benchmark=${benchmark}` : ''}`),
  theses: () => get('/portfolio/thesis'),
  saveThesis: (ticker, body) => put(`/portfolio/holdings/${encodeURIComponent(ticker)}/thesis`, body),
  addTrade: (t) => post('/portfolio/trades', t),
  deleteTrade: (id) => del(`/portfolio/trades/${id}`),

  getWatchlist: () => get('/watchlist'),
  addWatch: (w) => post('/watchlist', w),
  removeWatch: (t) => del(`/watchlist/${encodeURIComponent(t)}`),
  registerFact: (t, f) => post(`/watchlist/${encodeURIComponent(t)}/facts`, f),
  etfCatalog: () => get('/watchlist/catalog/etfs'),

  analyze: (ticker, assetType) =>
    get(`/analyze/${encodeURIComponent(ticker)}${assetType ? `?asset_type=${assetType}` : ''}`),
  ideas: (limit = 4) => get(`/ideas?limit=${limit}`),
  priceSeries: (ticker, days = 365) =>
    get(`/prices/${encodeURIComponent(ticker)}?days=${days}`),

  briefing: (includeIdeas = true) => get(`/briefing?include_ideas=${includeIdeas}`),
  alerts: (onlyUnread = false) => get(`/alerts?only_unread=${onlyUnread}`),
  refreshAlerts: () => post('/alerts/refresh'),
  markRead: (id) => post(`/alerts/${id}/read`),
  markAllRead: () => post('/alerts/read-all'),

  sources: () => get('/data/sources'),
  stockact: () => get('/data/stockact'),
  clearCache: () => post('/data/cache/clear'),
  exportUrl: `${BASE}/data/export`,
  wipe: () => del('/data/wipe?confirm=BORRAR'),
}
