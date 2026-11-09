"""Monitoreo de cobertura sobre la visita de León XIV a Uruguay.

Compatible con el CSV original. No verifica presencia visual ni sentimiento.
Ejecución: python scraper_papa.py
"""
import csv
import hashlib
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

RUTA = Path('data/menciones_papa_2026.csv')
DESDE = '2026-11-05'
HASTA_EXCLUSIVA = '2026-11-11'
LENGUAS = {
    'es': ('es-419', 'UY', 'UY:es-419'),
    'en': ('en-US', 'US', 'US:en'),
    'it': ('it', 'IT', 'IT:it'),
    'pt': ('pt-BR', 'BR', 'BR:pt-419'),
}
BUSQUEDAS = {
    'es': ['"León XIV" Uruguay', '"León XIV" Orsi', '"León XIV" Sodre',
           '"papa" "coro" "Montevideo"', '"papa" "orquesta" Uruguay'],
    'en': ['"Pope Leo XIV" Uruguay', '"Pope Leo XIV" Orsi',
           '"Pope Leo XIV" choir Uruguay', '"Sodre" Pope Uruguay'],
    'it': ['"Leone XIV" Uruguay', '"Leone XIV" coro Montevideo'],
    'pt': ['"Leão XIV" Uruguai', '"Leão XIV" Orsi'],
}
COLUMNAS_ORIGINALES = [
    'fecha', 'medio', 'titulo', 'enlace', 'nivel_coincidencia',
    'elenco_o_cuerpo', 'sentimiento', 'tema_principal'
]
COLUMNAS_NUEVAS = [
    'fecha_publicacion', 'fecha_relevamiento', 'idioma_busqueda',
    'consulta', 'tipo_mencion', 'aparicion_visual', 'evidencia_visual',
    'estado_revision', 'origen_contenido', 'identificador'
]


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    return ''.join(c for c in texto if not unicodedata.combining(c)).casefold()


def limpiar(texto):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', str(texto or ''))).split())


def categoria(titulo, resumen):
    texto = normalizar(titulo + ' ' + resumen)
    # Se buscan secuencias específicas: "coro" a secas no acredita participación.
    sodre = bool(re.search(r'\bsodre\b|\bossodre\b', texto))
    elencos = [
        ('Coro Nacional Juvenil', r'coro nacional juvenil'),
        ('Coro Nacional de Niños', r'coro nacional de ninos'),
        ('Orquesta Juvenil Nacional', r'orquesta juvenil nacional|uruguay(?:an)? national youth orchestra'),
        ('Coro Nacional', r'coro nacional(?! juvenil| de ninos)'),
        ('Orquesta Sinfónica Nacional', r'orquesta sinfonica nacional'),
    ]
    detectados = [nombre for nombre, patron in elencos if re.search(patron, texto)]
    hay_papa = bool(re.search(r'\bpapa\b|\bpope\b|\bpontifice\b|\bleon xiv\b|\bleo xiv\b|\bleone xiv\b|\bleao xiv\b', texto))
    hay_uruguay = bool(re.search(r'\buruguay\b|\buruguai\b|\bmontevideo\b|\borsi\b', texto))
    if not (hay_papa and hay_uruguay):
        return None, []
    if sodre:
        return 'A - Mención explícita Sodre (preliminar)', detectados
    if detectados:
        return 'A - Mención de elenco (preliminar)', detectados
    return 'D - Cobertura general', []


def fecha_entrada(entry):
    estructura = entry.get('published_parsed') or entry.get('updated_parsed')
    if estructura:
        return datetime(*estructura[:6], tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M')
    return ''


def descargar_feed(url):
    respuesta = requests.get(url, timeout=25, headers={'User-Agent': 'SodreMonitor/1.0 (RSS research)'})
    respuesta.raise_for_status()
    feed = feedparser.parse(respuesta.content)
    if feed.get('bozo') and not feed.entries:
        raise ValueError(f'RSS inválido: {feed.get("bozo_exception")}')
    return feed.entries

