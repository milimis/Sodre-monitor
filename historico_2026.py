import csv
import os
import re
import urllib.parse
from datetime import datetime
from typing import Literal, Optional
from dateutil import parser
import feedparser
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

CSV_PATH = "data/menciones_sodre_2026.csv"

# 1. ESQUEMA ESTRUCTURADO PARA GEMINI
class AnalisisMencionSodre(BaseModel):
    resumen_ejecutivo: str = Field(description="Resumen conciso (1-2 oraciones) de la mención.")
    sentimiento: Literal["positivo", "neutro", "negativo"] = Field(description="Sentimiento general.")
    elenco_o_cuerpo: Literal[
        "Ballet Nacional (BNS)",
        "Orquesta Sinfónica (OSSODRE)",
        "Coro Nacional",
        "Orquesta Juvenil",
        "Conjunto de Cámara",
        "Coro de Niños / Juvenil",
        "Área Lírica / Ópera",
        "Escuelas de Formación (ENFAS)",
        "Institucional / Autoridades / Varios",
        "Ninguno"
    ] = Field(description="Elenco o área específica.")
    tema_principal: Literal[
        "Crítica artística o reseña",
        "Cartelera y venta de entradas",
        "Gestión cultural y presupuesto",
        "Novedades institucionales o autoridades",
        "Entrevista a artistas o autoridades",
        "Otro"
    ] = Field(description="Eje temático principal.")
    obra_mencionada: Optional[str] = Field(default=None, description="Nombre de la obra si aplica.")

# Consultas específicas para Google News con filtro temporal 2026
CONSULTAS_HISTORICAS = [
    'Sodre after:2026-01-01',
    '"Auditorio Nacional Adela Reta" after:2026-01-01',
    '"Ballet Nacional del Sodre" after:2026-01-01',
    '"Orquesta Sinfónica del Sodre" OR OSSODRE after:2026-01-01',
    '"Coro Nacional del Sodre" after:2026-01-01',
    '"Auditorio Nelly Goitiño" after:2026-01-01',
    '"Auditorio Vaz Ferreira" after:2026-01-01',
    '"Sala Hugo Balzo" after:2026-01-01',
    '"Sala Eduardo Fabini" after:2026-01-01',
    'ENFAS Sodre after:2026-01-01',
    'BNS Sodre after:2026-01-01'
]

def obtener_enlaces_existentes():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {fila.get("enlace", "") for fila in reader}

def clasificar_con_gemini(client: genai.Client, titulo: str, texto: str) -> Optional[AnalisisMencionSodre]:
    texto_limpio = re.sub(r'<[^>]+>', ' ', texto)
    prompt = f"Analiza esta noticia cultural sobre el Sodre en Uruguay:\nTítulo: {titulo}\nTexto: {texto_limpio}"
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalisisMencionSodre,
                temperature=0.1
            ),
        )
        return AnalisisMencionSodre.model_validate_json(response.text)
    except Exception as e:
        print(f"Error con Gemini: {e}")
        return None

def main():
    os.makedirs("data", exist_ok=True)
    enlaces_previos = obtener_enlaces_existentes()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    nuevas_filas = []

    columnas = [
        "fecha", "medio", "titulo", "enlace", "nivel_coincidencia",
        "elenco_o_cuerpo", "sentimiento", "tema_principal",
        "obra_mencionada", "resumen_gemini", "keywords_detectadas"
    ]

    escribir_cabecera = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0

    for query in CONSULTAS_HISTORICAS:
        print(f"\nConsultando histórico: {query}...")
        query_codificada = urllib.parse.quote(query)
        url_rss = f"https://news.google.com/rss/search?q={query_codificada}&hl=es-419&gl=UY&ceid=UY:es-419"

        try:
            feed = feedparser.parse(url_rss)
            for entry in feed.entries:
                enlace = getattr(entry, "link", "")
                if not enlace or enlace in enlaces_previos:
                    continue

                titulo = getattr(entry, "title", "")
                resumen = getattr(entry, "summary", "")
                medio = entry.source.title if hasattr(entry, "source") else "Prensa Web"

                fecha = None
                if hasattr(entry, "published"):
                    fecha = parser.parse(entry.published)

                # Validar que pertenezca a 2026
                if fecha and fecha.year != 2026:
                    continue

                print(f"  -> Procesando nota histórica ({fecha.strftime('%d/%m/%Y') if fecha else 'S/F'}): {titulo[:60]}...")
                analisis = clasificar_con_gemini(client, titulo, resumen)

                fila = {
                    "fecha": fecha.strftime("%Y-%m-%d %H:%M") if fecha else "S/F",
                    "medio": medio,
                    "titulo": titulo.replace("\n", " ").strip(),
                    "enlace": enlace,
                    "nivel_coincidencia": "Búsqueda Histórica 2026",
                    "elenco_o_cuerpo": analisis.elenco_o_cuerpo if analisis else "No analizado",
                    "sentimiento": analisis.sentimiento if analisis else "No analizado",
                    "tema_principal": analisis.tema_principal if analisis else "No analizado",
                    "obra_mencionada": analisis.obra_mencionada if (analisis and analisis.obra_mencionada) else "-",
                    "resumen_gemini": (analisis.resumen_ejecutivo if analisis else resumen[:200]).replace("\n", " "),
                    "keywords_detectadas": query.split(" after:")[0]
                }
                nuevas_filas.append(fila)
                enlaces_previos.add(enlace)

        except Exception as e:
            print(f"Error procesando query '{query}': {e}")

    if nuevas_filas:
        with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            if escribir_cabecera:
                writer.writeheader()
            for r in nuevas_filas:
                writer.writerow(r)
        print(f"\n¡Éxito histórico! Se recuperaron {len(nuevas_filas)} noticias desde el 1 de enero de 2026.")
    else:
        print("\nNo se encontraron noticias adicionales para 2026.")

if __name__ == "__main__":
    main()
