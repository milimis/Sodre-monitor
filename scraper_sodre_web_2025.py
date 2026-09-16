import csv
import os
import re
import time
from datetime import datetime
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
        return {fila.get("enlace", "") for fila in reader}

def clasificar_con_gemini(client: genai.Client, titulo: str, texto: str) -> Optional[AnalisisMencionSodre]:
    prompt = f"Analiza esta mención de prensa oficial sobre el Sodre Uruguay:\nTítulo: {titulo}\nContexto: {texto}"
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    columnas = [
        "fecha", "medio", "titulo", "enlace", "nivel_coincidencia",
        "elenco_o_cuerpo", "sentimiento", "tema_principal",
        "obra_mencionada", "resumen_gemini", "keywords_detectadas"
    ]

    escribir_cabecera = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    nuevas_filas = []

    print("Iniciando extracción desde sodre.gub.uy/prensa/...")

    # Recorremos desde la página 1 hasta la 35 para cubrir todo el archivo
    for pg in range(1, 40):
        url = f"https://sodre.gub.uy/prensa/?pg={pg}" if pg > 1 else "https://sodre.gub.uy/prensa/"
        print(f"\n--- Explorando página {pg}: {url} ---")
        
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                print(f"Página {pg} no disponible o fin del listado (Status {r.status_code}).")
                break

            soup = BeautifulSoup(r.text, "html.parser")
            articulos = soup.find_all(["article", "div"], class_=lambda c: c and any(x in c for x in ["item-prensa", "noticia", "card", "post"]))
            
            if not articulos:
                articulos = soup.select("main a, .content a, article a")

            encontrados_en_pagina = 0

            # Buscar bloques de noticias
            items = soup.find_all(text=re.compile(r'\d{2}/\d{2}/2025'))
            if not items and pg > 15:
                # Si ya pasamos muchas páginas y no hay 2025, podemos haber llegado a 2024
                pass

            # Parseo general de links y textos con formato DD/MM/2025
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                texto_completo = a_tag.get_text(separator=" ", strip=True)
                
                # Buscar fecha 2025
                match_fecha = re.search(r'(\d{2}/\d{2}/2025)', texto_completo)
                if not match_fecha:
                    # Buscar en el padre
                    padre = a_tag.parent
                    if padre:
                        match_fecha = re.search(r'(\d{2}/\d{2}/2025)', padre.get_text())

                if match_fecha and "sodre.gub.uy/prensa/" in href:
                    if href in enlaces_previos:
                        continue

                    fecha_str = match_fecha.group(1)
                    titulo = a_tag.get_text(strip=True)
                    if len(titulo) < 15:
                        continue

                    # Extraer medio o etiquetas si existen en el contenedor
                    medio = "Prensa Relevada Sodre"
                    padre_text = a_tag.parent.get_text(" ", strip=True) if a_tag.parent else ""
                    
                    print(f"  [2025] Encontrada ({fecha_str}): {titulo[:60]}...")
                    analisis = clasificar_con_gemini(client, titulo, padre_text)

                    # Formatear fecha a YYYY-MM-DD
                    try:
                        d, m, y = fecha_str.split("/")
                        fecha_fmt = f"{y}-{m}-{d} 12:00"
                    except:
                        fecha_fmt = fecha_str

                    fila = {
                        "fecha": fecha_fmt,
                        "medio": medio,
                        "titulo": titulo,
                        "enlace": href,
                        "nivel_coincidencia": "Relevamiento Oficial Sodre Web",
                        "elenco_o_cuerpo": analisis.elenco_o_cuerpo if analisis else "No analizado",
                        "sentimiento": analisis.sentimiento if analisis else "No analizado",
                        "tema_principal": analisis.tema_principal if analisis else "No analizado",
                        "obra_mencionada": analisis.obra_mencionada if (analisis and analisis.obra_mencionada) else "-",
                        "resumen_gemini": (analisis.resumen_ejecutivo if analisis else titulo).replace("\n", " "),
                        "keywords_detectadas": "sodre.gub.uy/prensa"
                    }
                    nuevas_filas.append(fila)
                    enlaces_previos.add(href)
                    encontrados_en_pagina += 1

            print(f"Página {pg}: {encontrados_en_pagina} notas de 2025 recuperadas.")
            time.sleep(1)

        except Exception as e:
            print(f"Error procesando página {pg}: {e}")

    if nuevas_filas:
        with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            if escribir_cabecera:
                writer.writeheader()
            for r in nuevas_filas:
                writer.writerow(r)
        print(f"\n¡Total recuperado de la web del Sodre para 2025: {len(nuevas_filas)} noticias!")
    else:
        print("\nNo se pudieron extraer notas nuevas.")

if __name__ == "__main__":
    main()
