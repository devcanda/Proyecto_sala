#!/usr/bin/env python
"""
verificar_contrato_dom.py
--------------------------
Comprueba que el "contrato" entre el JavaScript y el HTML siga intacto.

Motivo (bitacora 2026-09-07, "Reconciliacion del layout de Retail estilo
Aronium"): una adaptacion visual hecha a mano borro #productos-grid y
#categorias-tabs y renombro #ticket-vacio. El resultado fue funcionalidad
muerta -- el buscador seguia ahi pero ya no filtraba nada -- SIN ningun
error visible en la consola del navegador. Un reskin no puede depender de
que alguien recuerde los 90+ identificadores que el JS busca a mano.

Que revisa:
  1. Todo id que el JS busca (getElementById / querySelector("#...")) existe
     en algun archivo HTML.
  2. Los enganches de navegacion por clase + atributo de datos siguen
     presentes (.seccion-btn[data-seccion], .modo-btn[data-modo]).
  3. Cada pantalla de venta sigue declarando su campo de captura del lector
     de codigo de barras ([data-captura-barras]); es una regla de UX
     critica: sin un campo enfocable, el lector deja de funcionar.

Uso:
    python scripts/verificar_contrato_dom.py

Codigo de salida 1 si encuentra algo roto, para poder usarlo en un hook de
pre-commit o en CI.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FRONTEND = RAIZ / "frontend"

# Selectores que el JS usa por clase/atributo en vez de por id. No se pueden
# deducir automaticamente sin un parser real, asi que se listan explicitamente.
# Ids que el JS consulta A PROPOSITO para saber si existen, y que pueden no
# estar en ninguna vista sin que eso sea un error. Van aqui solo si el JS los
# busca SIEMPRE con guarda (if (!el) return, o !!document.getElementById()).
# No es una via para silenciar huerfanos de verdad: cada entrada explica por
# que el JS sobrevive a su ausencia.
IDS_OPCIONALES = {
    "categorias-tabs": (
        "las pestañas de categoria se quitaron de Retail el 2026-09-08 y solo "
        "quedan en Inventario con otro id; renderCategoriasTabs() y "
        "productosFiltrados() ya salen sin hacer nada cuando no estan"
    ),
}

ENGANCHES_POR_CLASE = [
    (r'class="[^"]*\bseccion-btn\b[^"]*"[^>]*data-seccion=', ".seccion-btn[data-seccion]"),
    (r'data-seccion="[^"]*"[^>]*class="[^"]*\bseccion-btn\b', ".seccion-btn[data-seccion]"),
    (r'class="[^"]*\bmodo-btn\b[^"]*"[^>]*data-modo=', ".modo-btn[data-modo]"),
    (r'data-modo="[^"]*"[^>]*class="[^"]*\bmodo-btn\b', ".modo-btn[data-modo]"),
]


def ids_referenciados_por_js():
    """Ids que el JavaScript busca en el DOM, con el archivo y linea de origen."""
    referencias = {}
    for archivo_js in sorted(FRONTEND.glob("js/*.js")):
        for numero, linea in enumerate(archivo_js.read_text(encoding="utf-8").splitlines(), 1):
            for patron in (
                r'getElementById\(\s*["\']([^"\']+)["\']',
                r'querySelector\(\s*["\']#([A-Za-z0-9_-]+)["\']',
                r'querySelectorAll\(\s*["\']#([A-Za-z0-9_-]+)["\']',
            ):
                for id_encontrado in re.findall(patron, linea):
                    referencias.setdefault(id_encontrado, []).append(
                        f"{archivo_js.relative_to(RAIZ).as_posix()}:{numero}"
                    )
    return referencias


def ids_definidos_en_html():
    """Ids que realmente existen en el HTML (index + vistas inyectadas)."""
    definidos = {}
    archivos = [FRONTEND / "index.html"] + sorted(FRONTEND.glob("views/*.html"))
    for archivo in archivos:
        if not archivo.exists():
            continue
        texto = archivo.read_text(encoding="utf-8")
        for id_encontrado in re.findall(r'\bid="([^"]+)"', texto):
            definidos.setdefault(id_encontrado, []).append(
                archivo.relative_to(RAIZ).as_posix()
            )
    return definidos


def main():
    referencias = ids_referenciados_por_js()
    definidos = ids_definidos_en_html()

    problemas = []

    huerfanos = sorted(set(referencias) - set(definidos) - set(IDS_OPCIONALES))
    for id_huerfano in huerfanos:
        origen = ", ".join(referencias[id_huerfano])
        problemas.append(f"  #{id_huerfano} -- lo busca {origen}, no existe en ningun HTML")

    opcionales_ausentes = sorted(set(IDS_OPCIONALES) - set(definidos))

    html_completo = "\n".join(
        archivo.read_text(encoding="utf-8")
        for archivo in [FRONTEND / "index.html"] + sorted(FRONTEND.glob("views/*.html"))
        if archivo.exists()
    )

    for etiqueta in {etiqueta for _, etiqueta in ENGANCHES_POR_CLASE}:
        patrones = [p for p, e in ENGANCHES_POR_CLASE if e == etiqueta]
        if not any(re.search(p, html_completo) for p in patrones):
            problemas.append(f"  {etiqueta} -- enganche de navegacion ausente en el HTML")

    # El lector de codigo de barras ya no tiene campo propio: desde el
    # 2026-09-08 escribe en el buscador marcado con [data-captura-barras] de
    # cada pantalla de venta. Si una de esas vistas se queda sin el, el
    # lector deja de funcionar ahi y nada lo avisa.
    for vista in ("pos_retail.html", "pos_hospitalidad.html"):
        archivo = FRONTEND / "views" / vista
        if archivo.exists() and "data-captura-barras" not in archivo.read_text(encoding="utf-8"):
            problemas.append(
                f"  [data-captura-barras] -- ausente en views/{vista}; el lector "
                "de codigo de barras deja de funcionar en esa pantalla"
            )

    duplicados = sorted(i for i, archivos in definidos.items() if len(archivos) > 1)

    print(f"Ids buscados por el JS : {len(referencias)}")
    print(f"Ids definidos en el HTML: {len(definidos)}")
    print(f"Huerfanos               : {len(huerfanos)}")

    if opcionales_ausentes:
        print("\nOpcionales ausentes (declarados como tales, no son huerfanos):")
        for id_opcional in opcionales_ausentes:
            print(f"  #{id_opcional}: {IDS_OPCIONALES[id_opcional]}")

    if duplicados:
        print("\nAviso -- ids repetidos en mas de un archivo (solo importa si dos")
        print("vistas se muestran a la vez; hoy se inyecta una sola en #app-view):")
        for id_repetido in duplicados:
            print(f"  #{id_repetido}: {', '.join(definidos[id_repetido])}")

    if problemas:
        print("\nCONTRATO ROTO:")
        print("\n".join(problemas))
        return 1

    print("\nOK: el contrato entre el JS y el HTML esta intacto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
