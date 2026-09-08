/**
 * barcode.js
 * -----------
 * Captura de la entrada del lector de codigo de barras.
 *
 * CAMBIO 2026-09-08: el lector ya NO tiene un campo propio. Antes existia
 * un #barcode-input dedicado, fijo en la barra inferior de la ventana; se
 * quito por redundante (a pedido del desarrollador), y ahora el lector
 * escribe en el MISMO buscador de la pantalla. Ese buscador se marca en el
 * HTML con el atributo [data-captura-barras], que es lo unico que este
 * modulo busca.
 *
 * Responsabilidades:
 *   1. Mantener el foco en el campo de captura de la vista actual, siempre
 *      que sea visible, no haya un dialogo modal abierto y el usuario no
 *      este escribiendo en otro campo. Asi el lector (que emula tecleo +
 *      Enter) funciona sin que el operario tenga que tocar el mouse.
 *   2. Interpretar el Enter: soporta multiplicadores rapidos ("5*750123..."
 *      = 5 unidades) y emite el evento `barcode:scan` con { codigo, cantidad }.
 *
 * Este modulo NO conoce productos ni ordenes: solo parsea la entrada cruda
 * y avisa. Que hacer con ella lo decide app.js (ver onBarcodeScan), que
 * ademas es quien limpia el campo cuando el escaneo se resolvio.
 */
(function () {
  const SELECTOR_CAPTURA = "[data-captura-barras]";
  let modalAbierto = false;

  /**
   * Campo de captura de la vista actual, o null si no hay ninguno usable.
   * Las vistas se inyectan y se destruyen en cada cambio de pantalla, asi
   * que hay que buscarlo cada vez en lugar de guardarlo.
   */
  function campoCaptura() {
    const el = document.querySelector(SELECTOR_CAPTURA);
    if (!el) return null;
    // offsetParent en null significa que el elemento (o algun ancestro)
    // esta oculto. Pasa en Hospitalidad mientras se elige mesa: la cuenta,
    // con su buscador dentro, todavia no esta a la vista, y no tiene
    // sentido pelear por el foco de un campo que nadie ve.
    if (el.offsetParent === null) return null;
    return el;
  }

  // Campos donde el usuario esta escribiendo de verdad (formularios de
  // Productos, Inventario, Configuracion...): nunca robarles el foco.
  function esCampoEditable(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  }

  function enfocar() {
    if (modalAbierto) return;
    const campo = campoCaptura();
    if (!campo) return;
    if (document.activeElement === campo) return;
    if (esCampoEditable(document.activeElement)) return;
    campo.focus();
  }

  // Reintento barato pero insistente: cubre clics accidentales en otra
  // parte de la interfaz.
  document.addEventListener("click", (e) => {
    if (e.target !== campoCaptura()) {
      setTimeout(enfocar, 0);
    }
  });
  window.addEventListener("focus", enfocar);
  setInterval(enfocar, 1500);

  function parsearEntrada(raw) {
    // Formato multiplicador: "5*7501234567890" -> cantidad=5, codigo=7501234567890
    const match = raw.match(/^(\d+)\s*\*\s*(.+)$/);
    if (match) {
      return { cantidad: parseInt(match[1], 10), codigo: match[2].trim() };
    }
    return { cantidad: 1, codigo: raw.trim() };
  }

  // Delegado en document, no enlazado al campo: el campo de captura vive
  // dentro de las vistas que inyecta app.js, asi que nace y muere con cada
  // cambio de pantalla y no se le puede enlazar un listener una sola vez.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const campo = campoCaptura();
    if (!campo || e.target !== campo) return;
    e.preventDefault();

    const raw = campo.value;
    if (!raw.trim()) return;

    const { codigo, cantidad } = parsearEntrada(raw);
    // El campo NO se limpia aqui a proposito: si el codigo no se reconoce,
    // el texto tiene que quedar a la vista para que el operario lo corrija.
    // Lo limpia app.js con limpiar(), solo cuando el escaneo prospero.
    document.dispatchEvent(
      new CustomEvent("barcode:scan", { detail: { codigo, cantidad } })
    );
  });

  // API publica minima para app.js.
  window.barcodeFocus = {
    pausar: () => {
      modalAbierto = true;
    },
    reanudar: () => {
      modalAbierto = false;
      enfocar();
    },
    // Limpia el campo tras un escaneo resuelto y avisa al buscador, para
    // que la grilla vuelva a mostrarse sin el filtro que dejo el codigo.
    limpiar: () => {
      const campo = campoCaptura();
      if (!campo) return;
      campo.value = "";
      campo.dispatchEvent(new Event("input"));
    },
    enfocar,
    // Se expone para que el buscador de app.js interprete el multiplicador
    // igual que el lector: escribir "3*aceite" tiene que buscar "aceite" y
    // agregar 3, no buscar la cadena literal "3*aceite".
    parsear: parsearEntrada,
  };

  enfocar();
})();
