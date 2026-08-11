/**
 * Tema claro / oscuro.
 *
 * La aplicación se pinta según `data-theme` en <html>, que fija un script en
 * línea en index.html antes del primer pintado. Este módulo sólo cambia esa
 * misma marca cuando el usuario elige, y recuerda la elección.
 *
 * Tres estados y no dos: «automático» sigue al sistema, que es lo que casi
 * siempre se quiere, pero el sistema no siempre acierta —un Windows en claro
 * con la app abierta de madrugada— y forzarlo tiene que ser posible.
 */

const CLAVE = 'tema'
export const OPCIONES = ['auto', 'claro', 'oscuro']

/** Lo que el usuario eligió. `auto` si no eligió nada o si no hay almacenamiento. */
export function preferencia() {
  try {
    const v = localStorage.getItem(CLAVE)
    return OPCIONES.includes(v) ? v : 'auto'
  } catch {
    // Navegador con el almacenamiento bloqueado: se sigue con el del sistema
    // en lugar de romper la pantalla de ajustes.
    return 'auto'
  }
}

function consulta() {
  return window.matchMedia('(prefers-color-scheme: dark)')
}

/** El tema que se está aplicando de verdad: 'claro' u 'oscuro'. */
export function efectivo(pref = preferencia()) {
  if (pref === 'auto') return consulta().matches ? 'oscuro' : 'claro'
  return pref
}

function pintar(pref) {
  document.documentElement.dataset.theme = efectivo(pref) === 'oscuro' ? 'dark' : 'light'
}

export function elegir(pref) {
  if (!OPCIONES.includes(pref)) return
  try {
    localStorage.setItem(CLAVE, pref)
  } catch {
    /* sin almacenamiento el cambio dura hasta recargar, y es mejor que nada */
  }
  pintar(pref)
}

/**
 * Sigue los cambios del sistema mientras la preferencia sea «automático».
 *
 * Sin esto, poner el móvil en modo noche a las nueve no cambiaría nada hasta
 * recargar la página, que es justo cuando más se nota.
 */
export function seguirAlSistema() {
  const m = consulta()
  const alCambiar = () => preferencia() === 'auto' && pintar('auto')
  m.addEventListener('change', alCambiar)
  return () => m.removeEventListener('change', alCambiar)
}
