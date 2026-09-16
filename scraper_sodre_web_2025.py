import csv
import os
import re
import time
from typing import Literal, Optional
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

CSV_PATH = "data/menciones_sodre_2025.csv"

class AnalisisMencionSodre(BaseModel):
    resumen_ejecutivo: str = Field(description="Resumen conciso (1-2 oraciones).")
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
    ] = Field(description="Elenco o área.")
    tema_principal: Literal[
        "Crítica artística o reseña",
        "Cartelera y venta de entradas",
        "Gestión cultural y presupuesto",
        "Novedades institucionales o autoridades",
        "Entrevista a artistas o autoridades",
        "Otro"
    ] = Field(description="Tema.")
    obra_mencionada: Optional[str] = Field(default=None, description="Obra.")

def obtener_enlaces_existentes():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {fila.get("enlace", "") for fila in reader if fila.get("enlace")}

def clasificar_con_gemini(client: genai.Client, titulo: str, contexto: str) -> Optional[AnalisisMencionSodre]:
    prompt = f"Analiza esta mención de prensa oficial sobre el Sodre Uruguay:\nTítulo: {titulo}\nContexto: {contexto}"
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
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    columnas = [
        "fecha", "medio", "titulo", "enlace", "nivel_coincidencia",
        "elenco_o_cuerpo", "sentimiento", "tema_principal",
        "obra_mencionada", "resumen_gemini", "keywords_detectadas"
    ]

    escribir_cabecera = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    nuevas_filas = []

    print("Iniciando rastreo de páginas en sodre.gub.uy/prensa/...")

    # Recorrer páginas estándar de WordPress /prensa/ o /prensa/page/N/
    for page in range(1, 45):
        url = "https://sodre.gub.uy/prensa/" if page == 1 else f"https://sodre.gub.uy/prensa/page/{page}/"
        print(f"\nConsultando: {url}")
        
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code == 404:
                print("Llegamos al final del catálogo de prensa.")
                break
            if r.status_code != 200:
                print(f"Código HTTP {r.status_code}, reintentando...")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            
            # Buscar todos los textos con fechas en formato dd/mm/yyyy
            fechas_tags = soup.find_all(string=re.compile(r'\b\d{2}/\d{2}/(2025|2024)\b'))
            
            encontradas_en_pagina = 0
            for tag in fechas_tags:
                fecha_match = re.search(r'(\d{2}/\d{2}/2025)', str(tag))
                if not fecha_match:
                    continue  # Si es 2024 o 2026, lo salteamos

                fecha_str = fecha_match.group(1)
                
                # Obtener el contenedor padre de la noticia
                contenedor = tag.find_parent(["article", "div", "li", "tr"])
                if not contenedor:
                    continue

                # Extraer título y enlace
                enlace_tag = contenedor.find("a", href=True)
                enlace = enlace_tag["href"] if enlace_tag else ""
                
                # Si ya fue procesado, no repetir
                if enlace and enlace in enlaces_previos:
                    continue

                titulo = ""
                # Priorizar el texto del enlace o encabezado H2/H3/H4
                h_tag = contenedor.find(["h2", "h3", "h4", "h5", "a"])
                if h_tag:
                    titulo = h_tag.get_text(strip=True)
                if not titulo or len(titulo) < 10:
                    titulo = contenedor.get_text(" ", strip=True)
                    # Quitar la fecha del texto del título
                    titulo = titulo.replace(fecha_str, "").strip()

                if len(titulo) < 10:
                    continue

                # Intentar detectar el medio
                medio = "Prensa Relevada Sodre"
                texto_bloque = contenedor.get_text(" ", strip=True)
                for posible_medio in ["El País", "El Observador", "la diaria", "Búsqueda", "Montevideo Portal", "Uypress", "VTV", "Canal 5", "Canal 10", "Telemundo", "Subrayado", "Radio Sarandí", "Radio Uruguay", "En Perspectiva"]:
                    if posible_medio.lower() in texto_bloque.lower():
                        medio = posible_medio
                        break

                print(f"  -> Nota 2025: [{fecha_str}] [{medio}] {titulo[:50]}...")
                analisis = clasificar_con_gemini(client, titulo, texto_bloque)

                try:
                    d, m, y = fecha_str.split("/")
                    fecha_fmt = f"{y}-{m}-{d} 12:00"
                except:
                    fecha_fmt = fecha_str

                fila = {
                    "fecha": fecha_fmt,
                    "medio": medio,
                    "titulo": titulo.replace("\n", " ").strip(),
                    "enlace": enlace if enlace else f"https://sodre.gub.uy/prensa/#2025-{len(nuevas_filas)}",
                    "nivel_coincidencia": "Relevamiento Sodre Prensa Oficial",
                    "elenco_o_cuerpo": analisis.elenco_o_cuerpo if analisis else "No analizado",
                    "sentimiento": analisis.sentimiento if analisis else "No analizado",
                    "tema_principal": analisis.tema_principal if analisis else "No analizado",
                    "obra_mencionada": analisis.obra_mencionada if (analisis and analisis.obra_mencionada) else "-",
                    "resumen_gemini": (analisis.resumen_ejecutivo if analisis else titulo).replace("\n", " "),
                    "keywords_detectadas": "sodre.gub.uy/prensa 2025"
                }
                nuevas_filas.append(fila)
                if enlace:
                    enlaces_previos.add(enlace)
                encontradas_en_pagina += 1

            print(f"Página {page}: {encontradas_en_pagina} notas de 2025 procesadas.")
            time.sleep(0.5)

        except Exception as e:
            print(f"Error procesando página {page}: {e}")

    if nuevas_filas:
        with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            if escribir_cabecera:
                writer.writeheader()
            for r in nuevas_filas:
                writer.writerow(r)
        print(f"\n¡Éxito! Se añadieron {len(nuevas_filas)} menciones oficiales de 2025 a {CSV_PATH}.")
    else:
        print("\nNo se detectaron nuevas notas de 2025.")

if __name__ == "__main__":
    main()
