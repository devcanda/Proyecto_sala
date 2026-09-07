/**
 * barcode.js
 * -----------
 * Gestion del campo #barcode-input (documento maestro, seccion 5-B):
 *
 * 1. Mantiene el foco en ese input SIEMPRE que no haya un modal abierto,
 *    para que un lector de codigo de barras (que emula tecleo + Enter)
 *    funcione sin que el operario toque el mouse.
 * 2. Soporta multiplicadores rapidos: escribir "5*" antes de escanear/tipear
 *    un codigo hace que la cantidad se interprete como 5 en vez de 1.
 *
 * Este modulo NO conoce productos ni ordenes: solo parsea la entrada cruda
 * y emite un evento `barcode:scan` con { codigo, cantidad } para que
 * app.js decida que hacer (buscar producto, agregarlo a la orden, etc).
 */
(function () {
  const input = document.getElementById("barcode-input");
  let modalAbierto = false;

  function enfocar() {
    if (!modalAbierto && document.activeElement !== input) {
      input.focus();
    }
  }

  // Reintenta el foco de forma agresiva pero barata: cubre casos como un
  // click accidental en otra parte de la UI.
  document.addEventListener("click", (e) => {
    if (e.target !== input) {
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

  input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();

    const raw = input.value;
    input.value = "";
    if (!raw.trim()) return;

    const { codigo, cantidad } = parsearEntrada(raw);
    document.dispatchEvent(
      new CustomEvent("barcode:scan", { detail: { codigo, cantidad } })
    );
  });

  // API publica minima para que app.js pueda pausar el foco al abrir dialogos.
  window.barcodeFocus = {
    pausar: () => {
      modalAbierto = true;
    },
    reanudar: () => {
      modalAbierto = false;
      enfocar();
    },
  };

  enfocar();
})();
