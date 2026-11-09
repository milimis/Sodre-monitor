
"""
SODRE - MONITOREO INTERNACIONAL
Visita del papa León XIV a Uruguay - Noviembre 2026

Relevamiento específico:
1. Papa León XIV y Yamandú Orsi
2. Papa León XIV y Uruguay
3. Papa León XIV y Sodre / elencos

No incorpora datos del scraper anterior.
"""

import csv
import re
import html
import os
import tempfile
import unicodedata

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode

import feedparser
import requests


# ==================================================
# CONFIGURACIÓN
# ==================================================

SALIDA = Path("data/menciones_papa_filtradas_2026.csv")

DESDE = "2026-11-05"
HASTA = "2026-11-11"

IDIOMAS = {
    "es": ("es-419", "UY", "UY:es-419"),
    "en": ("en-US", "US", "US:en"),
    "it": ("it", "IT", "IT:it"),
    "pt": ("pt-BR", "BR", "BR:pt-419"),
}

BUSQUEDAS = {
    "es": [
        '"León XIV" "Orsi"',
        '"León XIV" "Uruguay"',
        '"León XIV" "Montevideo"',
        '"papa" "Sodre"',
        '"papa" "Orquesta Juvenil Nacional"',
        '"papa" "Coro Nacional" "Uruguay"',
    ],
    "en": [
        '"Pope Leo XIV" "Orsi"',
        '"Pope Leo XIV" "Uruguay"',
        '"Pope Leo XIV" "Montevideo"',
        '"Pope Leo XIV" "Sodre"',
        '"Pope Leo XIV" "choir" "Uruguay"',
    ],
    "it": [
        '"Leone XIV" "Uruguay"',
        '"Leone XIV" "Orsi"',
        '"Leone XIV" "Montevideo"',
    ],
    "pt": [
        '"Leão XIV" "Uruguai"',
        '"Leão XIV" "Orsi"',
        '"Leão XIV" "Montevidéu"',
    ],
}

COLUMNAS = [
    "fecha",
    "medio",
    "titulo",
    "enlace",
    "nivel_coincidencia",
    "elenco_o_cuerpo",
    "sentimiento",
    "tema_principal",
    "fecha_publicacion",
    "idioma_busqueda",
    "tipo_mencion",
    "aparicion_visual",
    "evidencia_visual",
    "estado_revision",
]


# ==================================================
# LIMPIEZA DE TEXTO
# ==================================================

def normalizar(texto):
    texto = unicodedata.normalize(
        "NFKD", str(texto or "")
    )
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return texto.lower().strip()


def limpiar(texto):
    texto = re.sub(r"<[^>]+>", " ", str(texto or ""))
    return " ".join(html.unescape(texto).split())


# ==================================================
# FILTRO ESTRICTO DE RELEVANCIA
# ==================================================

PAPA = (
    r"\bpapa\b|\bpope\b|\bpontifice\b|"
    r"\bleon xiv\b|\bleo xiv\b|"
    r"\bleone xiv\b|\bleao xiv\b|"
    r"\bleon 14\b|\bleo 14\b"
)

URUGUAY = (
    r"\buruguay\b|\buruguai\b|"
    r"\bmontevideo\b|\bmontevideu\b|"
    r"\borsi\b|\bcarrasco\b"
)

SODRE = r"\bsodre\b|\bossodre\b"

ELENCOS = {
    "Coro Nacional": r"\bcoro nacional\b",
    "Coro Nacional Juvenil": r"\bcoro nacional juvenil\b",
    "Coro Nacional de Niños": r"\bcoro nacional de ninos\b",
    "Orquesta Juvenil Nacional":
        r"\borquesta juvenil nacional\b",
    "Orquesta Sinfónica Nacional":
        r"\borquesta sinfonica nacional\b|\bossodre\b",
}


def clasificar(titulo, resumen):
    t = normalizar(titulo)
    r = normalizar(resumen)
    texto = t + " " + r

    # Primero: el título tiene que tratar sobre el papa.
    if not re.search(PAPA, t):
        return None

    # Segundo: relación explícita en el título.
    relacionado = (
        re.search(URUGUAY, t)
        or re.search(SODRE, t)
        or any(
            re.search(patron, t)
            for patron in ELENCOS.values()
        )
    )

    if not relacionado:
        return None

    detectados = [
        nombre
        for nombre, patron in ELENCOS.items()
        if re.search(patron, texto)
    ]

    if "Coro Nacional Juvenil" in detectados:
        if "Coro Nacional" in detectados:
            detectados.remove("Coro Nacional")

    if "Coro Nacional de Niños" in detectados:
        if "Coro Nacional" in detectados:
            detectados.remove("Coro Nacional")

    if re.search(SODRE, texto):
        categoria = "A - Sodre (preliminar)"

    elif detectados:
        categoria = "B - Elencos (preliminar)"

    elif re.search(r"\borsi\b", t):
        categoria = "C - Papa y Orsi"

    else:
        categoria = "D - Papa en Uruguay"

    return categoria, detectados


# ==================================================
# CONSULTAS RSS
# ==================================================

def crear_url(consulta, idioma):
    hl, gl, ceid = IDIOMAS[idioma]

    parametros = {
        "q": (
            f"{consulta} "
            f"after:{DESDE} before:{HASTA}"
        ),
        "hl": hl,
        "gl": gl,
        "ceid": ceid,
    }

    return (
        "https://news.google.com/rss/search?"
        + urlencode(parametros)
    )


def fecha_noticia(entry):
    estructura = (
        entry.get("published_parsed")
        or entry.get("updated_parsed")
    )

    if not estructura:
        return ""

    return datetime(
        *estructura[:6],
        tzinfo=timezone.utc
    ).strftime("%Y-%m-%d %H:%M")


# ==================================================
# RECOLECCIÓN
# ==================================================

def buscar_noticias():
    registros = []
    enlaces = set()

    ahora = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M")

    for idioma, consultas in BUSQUEDAS.items():

        for consulta in consultas:
            print(f"Buscando: {consulta}")

            try:
                respuesta = requests.get(
                    crear_url(consulta, idioma),
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
                    print("RSS inválido. Se omite.")
                    continue

            except Exception as error:
                print(f"Error RSS: {error}")
                continue

            for entry in feed.entries:

                titulo = limpiar(
                    entry.get("title", "")
                )

                resumen = limpiar(
                    entry.get("summary", "")
                )

                enlace = entry.get("link", "")

                if not titulo or not enlace:
                    continue

                fecha = fecha_noticia(entry)

                if fecha and not (
                    DESDE <= fecha[:10] < HASTA
                ):
                    continue

                clasificacion = clasificar(
                    titulo, resumen
                )

                if clasificacion is None:
                    continue

                clave = enlace.strip().rstrip("/")

                if clave in enlaces:
                    continue

                enlaces.add(clave)

                categoria, elencos = clasificacion

                medio = entry.get(
                    "source", {}
                ).get(
                    "title", "No identificado"
                )

                registros.append({
                    "fecha": ahora,
                    "medio": medio,
                    "titulo": titulo,
                    "enlace": enlace,
                    "nivel_coincidencia": categoria,
                    "elenco_o_cuerpo": ", ".join(elencos),
                    "sentimiento": "Sin evaluar",
                    "tema_principal": "Visita Papal",
                    "fecha_publicacion": fecha,
                    "idioma_busqueda": idioma,
                    "tipo_mencion": categoria,
                    "aparicion_visual": "Sin verificar",
                    "evidencia_visual": "",
                    "estado_revision": "Pendiente",
                })

    return registros


# ==================================================
# GUARDADO INDEPENDIENTE
# ==================================================

def guardar(registros):

    if not registros:
        print(
            "No se encontraron noticias. "
            "No se modificará el CSV."
        )
        return

    SALIDA.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporal = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            delete=False,
            dir=SALIDA.parent,
            suffix=".tmp"
        ) as archivo:

            temporal = archivo.name

            escritor = csv.DictWriter(
                archivo,
                fieldnames=COLUMNAS
            )

            escritor.writeheader()
            escritor.writerows(registros)

        os.replace(temporal, SALIDA)

    finally:
        if temporal and os.path.exists(temporal):
            os.remove(temporal)

    print("\nRELEVAMIENTO FINALIZADO")
    print(f"Noticias filtradas: {len(registros)}")
    print(f"Archivo: {SALIDA}")

    for categoria in sorted(
        set(r["tipo_mencion"] for r in registros)
    ):
        cantidad = sum(
            r["tipo_mencion"] == categoria
            for r in registros
        )
        print(f"{categoria}: {cantidad}")


# ==================================================
# EJECUCIÓN
# ==================================================

if __name__ == "__main__":
    guardar(buscar_noticias())
