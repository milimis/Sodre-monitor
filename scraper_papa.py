
"""
SODRE - MONITOR DE REPERCUSIÓN INTERNACIONAL
Visita del papa León XIV a Uruguay - Noviembre 2026

Fuentes: Google News RSS
Idiomas: español, inglés, italiano y portugués

Compatible con el CSV original.
No verifica automáticamente fotografías, videos ni sentimientos.
"""

import csv
import html
import os
import re
import shutil
import tempfile
import unicodedata

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import feedparser
import requests


# ==========================================================
# 1. CONFIGURACIÓN GENERAL
# ==========================================================

ARCHIVO = Path("data/menciones_papa_2026.csv")

FECHA_DESDE = "2026-11-05"
FECHA_HASTA = "2026-11-11"  # Exclusiva: incluye hasta el día 10

IDIOMAS = {
    "es": ("es-419", "UY", "UY:es-419"),
    "en": ("en-US", "US", "US:en"),
    "it": ("it", "IT", "IT:it"),
    "pt": ("pt-BR", "BR", "BR:pt-419"),
}

BUSQUEDAS = {
    "es": [
        '"León XIV" Uruguay',
        '"León XIV" Orsi',
        '"León XIV" Sodre',
        '"papa" "coro" "Montevideo"',
        '"papa" "orquesta" Uruguay',
        '"visita papal" Uruguay',
    ],
    "en": [
        '"Pope Leo XIV" Uruguay',
        '"Pope Leo XIV" Orsi',
        '"Pope Leo XIV" choir Uruguay',
        '"Pope Leo XIV" orchestra Uruguay',
        '"Sodre" Pope Uruguay',
    ],
    "it": [
        '"Leone XIV" Uruguay',
        '"Leone XIV" Montevideo',
        '"Leone XIV" coro Uruguay',
    ],
    "pt": [
        '"Leão XIV" Uruguai',
        '"Leão XIV" Orsi',
        '"Leão XIV" coral Uruguai',
    ],
}

COLUMNAS_ORIGINALES = [
    "fecha",
    "medio",
    "titulo",
    "enlace",
    "nivel_coincidencia",
    "elenco_o_cuerpo",
    "sentimiento",
    "tema_principal",
]

COLUMNAS_NUEVAS = [
    "fecha_publicacion",
    "fecha_relevamiento",
    "idioma_busqueda",
    "consulta",
    "tipo_mencion",
    "aparicion_visual",
    "evidencia_visual",
    "estado_revision",
    "origen_contenido",
]


# ==========================================================
# 2. FUNCIONES DE LIMPIEZA
# ==========================================================

def normalizar(texto):
    texto = unicodedata.normalize(
        "NFKD",
        str(texto or "")
    )
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return texto.lower().strip()


def limpiar_html(texto):
    texto = re.sub(
        r"<[^>]+>",
        " ",
        str(texto or "")
    )
    return " ".join(
        html.unescape(texto).split()
    )


# ==========================================================
# 3. DETECCIÓN DE ELENCOS
# ==========================================================

PATRONES_ELENCOS = {
    "Coro Nacional Juvenil": [
        "coro nacional juvenil",
        "national youth choir",
    ],
    "Coro Nacional de Niños": [
        "coro nacional de ninos",
        "national children's choir",
    ],
    "Orquesta Juvenil Nacional": [
        "orquesta juvenil nacional",
        "national youth orchestra of uruguay",
        "uruguayan national youth orchestra",
    ],
    "Orquesta Sinfónica Nacional": [
        "orquesta sinfonica nacional",
        "ossodre",
    ],
    "Coro Nacional": [
        "coro nacional",
        "national choir of uruguay",
    ],
}


def detectar_elencos(texto):
    texto = normalizar(texto)
    encontrados = []

    for nombre, variantes in PATRONES_ELENCOS.items():
        if any(v in texto for v in variantes):
            encontrados.append(nombre)

    # Evitar contar el Coro Nacional cuando solamente
    # aparece una mención al Coro Nacional Juvenil
    # o al Coro Nacional de Niños.
    if "Coro Nacional" in encontrados:
        texto_sin_subgrupos = texto.replace(
            "coro nacional juvenil", ""
        ).replace(
            "coro nacional de ninos", ""
        )

        if (
            "coro nacional" not in texto_sin_subgrupos
            and "national choir of uruguay" not in texto
        ):
            encontrados.remove("Coro Nacional")

    return encontrados


# ==========================================================
# 4. CLASIFICACIÓN DE NOTICIAS
# ==========================================================

def clasificar(titulo, resumen):
    texto = normalizar(
        f"{titulo} {resumen}"
    )

    menciona_sodre = bool(
        re.search(
            r"\bsodre\b|\bossodre\b",
            texto
        )
    )

    elencos = detectar_elencos(texto)

    menciona_papa = bool(
        re.search(
            r"\bpapa\b|\bpope\b|\bpontifice\b|"
            r"\bleon xiv\b|\bleo xiv\b|"
            r"\bleone xiv\b|\bleao xiv\b",
            texto
        )
    )

    menciona_uruguay = bool(
        re.search(
            r"\buruguay\b|\buruguai\b|"
            r"\bmontevideo\b|\borsi\b",
            texto
        )
    )

    # La noticia debe estar relacionada con la visita.
    if not (menciona_papa and menciona_uruguay):
        return None, []

    if menciona_sodre:
        return (
            "A - Mención Sodre (preliminar)",
            elencos
        )

    if elencos:
        return (
            "A - Mención elenco (preliminar)",
            elencos
        )

    return (
        "D - Cobertura general",
        []
    )


# ==========================================================
# 5. FECHAS DE PUBLICACIÓN
# ==========================================================

def fecha_publicacion(entry):
    fecha = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not fecha:
        return ""

    return datetime(
        *fecha[:6],
        tzinfo=timezone.utc
    ).strftime("%Y-%m-%d %H:%M")


# ==========================================================
# 6. CONSULTAS A GOOGLE NEWS
# ==========================================================

def url_google_news(consulta, idioma):
    hl, gl, ceid = IDIOMAS[idioma]

    parametros = {
        "q": (
            f"{consulta} "
            f"after:{FECHA_DESDE} "
            f"before:{FECHA_HASTA}"
        ),
        "hl": hl,
        "gl": gl,
        "ceid": ceid,
    }

    return (
        "https://news.google.com/rss/search?"
        + urlencode(parametros)
    )


def descargar_rss(url):
    respuesta = requests.get(
        url,
        timeout=25,
        headers={
            "User-Agent": "SodreMonitor/1.0"
        }
    )

    respuesta.raise_for_status()

    feed = feedparser.parse(
        respuesta.content
    )

    if feed.get("bozo") and not feed.entries:
        raise ValueError(
            "Google News devolvió un RSS inválido"
        )

    return feed.entries


# ==========================================================
# 7. RECOLECCIÓN DE NOTICIAS
# ==========================================================

def recopilar_noticias():
    resultados = []

    ahora = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M")

    for idioma, consultas in BUSQUEDAS.items():

        for consulta in consultas:
            print(
                f"Buscando [{idioma}]: {consulta}"
            )

            url = url_google_news(
                consulta,
                idioma
            )

            try:
                entradas = descargar_rss(url)

            except Exception as error:
                print(
                    f"Error consultando RSS: {error}"
                )
                continue

            for entry in entradas:

                titulo = limpiar_html(
                    entry.get("title", "")
                )

                resumen = limpiar_html(
                    entry.get("summary", "")
                )

                enlace = entry.get("link", "")

                if not titulo or not enlace:
                    continue

                fecha_original = fecha_publicacion(
                    entry
                )

                # Excluir noticias publicadas fuera
                # del período definido.
                if fecha_original:
                    dia = fecha_original[:10]

                    if not (
                        FECHA_DESDE <= dia < FECHA_HASTA
                    ):
                        continue

                categoria, elencos = clasificar(
                    titulo,
                    resumen
                )

                if categoria is None:
                    continue

                fuente = entry.get("source", {})

                medio = fuente.get(
                    "title",
                    "No identificado"
                )

                registro = {
                    "fecha": ahora,
                    "medio": medio,
                    "titulo": titulo,
                    "enlace": enlace,
                    "nivel_coincidencia": categoria,
                    "elenco_o_cuerpo": (
                        ", ".join(elencos)
                        if elencos
                        else "No identificado"
                    ),
                    "sentimiento": "Sin evaluar",
                    "tema_principal": "Visita Papal",
                    "fecha_publicacion": fecha_original,
                    "fecha_relevamiento": ahora,
                    "idioma_busqueda": idioma,
                    "consulta": consulta,
                    "tipo_mencion": categoria,
                    "aparicion_visual": "Sin verificar",
                    "evidencia_visual": "",
                    "estado_revision": "Pendiente",
                    "origen_contenido": "Sin verificar",
                }

                resultados.append(registro)

    print(
        f"Registros encontrados: {len(resultados)}"
    )

    return resultados


# ==========================================================
# 8. LEER HISTÓRICO
# ==========================================================

def leer_historico():

    if not ARCHIVO.exists():
        return [], COLUMNAS_ORIGINALES + COLUMNAS_NUEVAS

    with ARCHIVO.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as archivo:

        lector = csv.DictReader(archivo)

        if not lector.fieldnames:
            raise ValueError(
                "El CSV existente no tiene encabezados"
            )

        if "enlace" not in lector.fieldnames:
            raise ValueError(
                "El CSV no tiene columna enlace"
            )

        columnas = list(lector.fieldnames)
        anteriores = list(lector)

    for columna in (
        COLUMNAS_ORIGINALES + COLUMNAS_NUEVAS
    ):
        if columna not in columnas:
            columnas.append(columna)

    return anteriores, columnas


# ==========================================================
# 9. EVITAR DUPLICADOS
# ==========================================================

def clave_noticia(registro):
    enlace = str(
        registro.get("enlace", "")
    ).strip().rstrip("/")

    if enlace:
        return ("url", enlace)

    titulo = normalizar(
        registro.get("titulo", "")
    )

    medio = normalizar(
        registro.get("medio", "")
    )

    return ("titulo", titulo, medio)


def acumular(anteriores, nuevas):
    resultado = list(anteriores)

    claves = {
        clave_noticia(fila)
        for fila in anteriores
    }

    agregadas = 0

    for noticia in nuevas:
        clave = clave_noticia(noticia)

        if clave in claves:
            continue

        claves.add(clave)
        resultado.append(noticia)
        agregadas += 1

    return resultado, agregadas


# ==========================================================
# 10. GUARDADO SEGURO
# ==========================================================

def guardar_csv(registros, columnas):
    ARCHIVO.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Respaldar el archivo existente.
    if ARCHIVO.exists():
        sello = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S_%f")

        respaldo = ARCHIVO.with_name(
            f"{ARCHIVO.stem}_backup_{sello}.csv"
        )

        shutil.copy2(
            ARCHIVO,
            respaldo
        )

        print(f"Respaldo creado: {respaldo}")

    # Escribir primero en un archivo temporal.
    temporal = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            delete=False,
            dir=ARCHIVO.parent,
            suffix=".tmp"
        ) as archivo:

            temporal = archivo.name

            escritor = csv.DictWriter(
                archivo,
                fieldnames=columnas,
                extrasaction="ignore"
            )

            escritor.writeheader()
            escritor.writerows(registros)

        # Reemplazar únicamente después
        # de escribir correctamente.
        os.replace(
            temporal,
            ARCHIVO
        )

    finally:
        if temporal and os.path.exists(temporal):
            os.remove(temporal)


# ==========================================================
# 11. EJECUCIÓN PRINCIPAL
# ==========================================================

def main():

    print("\nMONITOR INTERNACIONAL SODRE")
    print("Visita del papa León XIV\n")

    anteriores, columnas = leer_historico()

    print(
        f"Registros anteriores: {len(anteriores)}"
    )

    nuevas = recopilar_noticias()

    finales, agregadas = acumular(
        anteriores,
        nuevas
    )

    if agregadas == 0:
        print(
            "\nNo hay noticias nuevas para guardar."
        )
        return

    guardar_csv(
        finales,
        columnas
    )

    print("\nMONITOREO FINALIZADO")
    print(f"Noticias agregadas: {agregadas}")
    print(f"Total acumulado: {len(finales)}")
    print(f"Archivo: {ARCHIVO}")


if __name__ == "__main__":
    main()
