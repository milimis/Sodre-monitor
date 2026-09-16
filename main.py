import csv
import os
import re
from datetime import datetime
from typing import Literal, Optional
from dateutil import parser
import feedparser
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

CSV_PATH = "data/menciones_sodre_2026.csv"
ANO_OBJETIVO = 2026

# ==========================================
# 1. ESQUEMA ESTRUCTURADO PARA GEMINI
# ==========================================
class AnalisisMencionSodre(BaseModel):
    resumen_ejecutivo: str = Field(
        description="Resumen conciso (1-2 oraciones) de la mención sobre el Sodre o sus actividades."
    )
    sentimiento: Literal["positivo", "neutro", "negativo"] = Field(
        description="Sentimiento o tono general hacia la institución, el elenco o la obra."
    )
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
    ] = Field(description="Elenco, cuerpo artístico o área específica protagonista.")
    tema_principal: Literal[
        "Crítica artística o reseña",
        "Cartelera y venta de entradas",
        "Gestión cultural y presupuesto",
        "Novedades institucionales o autoridades",
        "Entrevista a artistas o autoridades",
        "Otro"
    ] = Field(description="Eje temático principal de la publicación.")
    obra_mencionada: Optional[str] = Field(
        default=None,
        description="Nombre específico de la obra o concierto si aplica (ej. Coppélia, El Cascanueces). Si no aplica, null."
    )

# ==========================================
# 2. TAXONOMÍA Y PALABRAS CLAVE
# ==========================================

# Nivel 1: Marca institucional directa y elencos (Match directo)
KEYWORDS_L1 = [
    r"\bsodre\b", r"servicio oficial de difusión, representaciones y espectáculos",
    r"auditorio nacional adela reta", r"auditorio adela reta",
    r"auditorio nelly goitiño", r"auditorio vaz ferreira",
    r"ballet nacional del sodre", r"ballet nacional sodre", r"\bbns\b",
    r"orquesta sinfónica del sodre", r"\bossodre\b",
    r"coro nacional del sodre", r"conjunto nacional de música de cámara",
    r"orquesta juvenil del sodre", r"coro nacional de niños", r"coro nacional juvenil",
    r"área lírica", r"ópera sodre", r"\benfas\b",
    r"escuelas de formación artística del sodre", r"\banip\b",
    r"archivo nacional de la imagen y la palabra",
    r"consejo directivo del sodre", r"consejo directivo sodre"
]

# Nivel 2: Salas ambiguas, autoridades y MEC (Requieren contexto)
KEYWORDS_L2 = [
    r"adela reta", r"sala eduardo fabini", r"sala fabini",
    r"sala hugo balzo", r"sala balzo", r"nelly goitiño",
    r"vaz ferreira", r"sala vaz ferreira",
    r"luis pérez aquino", r"alejandra moreira", r"natalia schiavone",
    r"ministerio de educación y cultura", r"\bmec\b",
    r"josé carlos mahía", r"gabriela verde", r"carlos varela",
    r"carlos varela ubal", r"dirección nacional de cultura", r"maría eugenia vidal"
]

# Nivel 3: Títulos de espectáculos y cartelera (Requieren anclas institucionales)
KEYWORDS_L3 = [
    r"coppélia", r"coppelia", r"el cascanueces", r"conciertos en familia", r"homero francesch"
]

# Contexto cultural asociado
KEYWORDS_CONTEXTO = [
    r"\buruguay\b", r"\bmontevideo\b", r"\bcultura\b", r"\bballet\b",
    r"\bdanza\b", r"\bópera\b", r"\bopera\b", r"\borquesta\b",
    r"\bsinfónica\b", r"\bcoro\b", r"\bconcierto\b", r"\brecital\b",
    r"\bauditorio\b", r"\bteatro\b", r"\bentradas\b", r"\btickantel\b",
    r"\btemporada\b", r"\babono\b", r"\bestreno\b", r"\bfunción\b", r"\bfuncion\b"
]

# Entidades de medios, programas y marcas periodísticas
KEYWORDS_MEDIOS = [
    r"medios públicos", r"secan", r"servicio de comunicación audiovisual nacional",
    r"canal 5", r"canal cinco", r"tnu", r"televisión nacional uruguay",
    r"canal 5 noticias", r"info tnu",
    r"radio uruguay", r"cx26", r"rnu", r"uruguay 1050",
    r"babel", r"radio babel", r"babel fm", r"97\.1 fm",
    r"clásica 650", r"radio clásica", r"cx6",
    r"radio cultura", r"cultura 1290", r"emisora del sur", r"cx38",
    r"telenoche", r"canal 4", r"monte carlo tv",
    r"subrayado", r"canal 10", r"saeta",
    r"telemundo", r"canal 12", r"teledoce", r"la tele",
    r"tv ciudad", r"tvciudad",
    r"vtv uruguay", r"\bvtv\b", r"cardinal tv", r"nuevo siglo", r"\bnstv\b",
    r"en perspectiva", r"radiomundo", r"cx32", r"emiliano cotelo",
    r"radio monte carlo", r"radio montecarlo", r"cx20",
    r"radio sarandí", r"sarandí 690", r"cx8",
    r"el espectador", r"el espectador 810", r"cx14",
    r"del sol fm", r"\bdelsol\b",
    r"azul fm", r"101\.9 fm",
    r"\bm24\b", r"m24 radio",
    r"cx36", r"radio centenario",
    r"970 universal", r"radio universal", r"cx22",
    r"radio carve", r"carve 850", r"cx16",
    r"radio oriental", r"oriental 770", r"cx12",
    r"océano fm", r"radio cero", r"radio nuevo tiempo",
    r"la república", r"diario la república", r"lr21", r"la red 21",
    r"el popular", r"diario la juventud", r"crónicas económicas",
    r"el telégrafo", r"diario el pueblo", r"\bagesor\b",
    r"maldonado noticias", r"san josé ahora"
]

# Directorio de feeds RSS activos
FEEDS = {
    "La Diaria": "https://ladiaria.com.uy/feed/",
    "El País": "https://www.elpais.com.uy/rss",
    "Montevideo Portal": "https://www.montevideo.com.uy/anxml.aspx?58",
    "El Observador": "https://www.elobservador.com.uy/rss/cultura.xml",
    "Subrayado (Canal 10)": "https://www.subrayado.com.uy/rss/cultura.xml",
    "Telemundo (Canal 12)": "https://www.teledoce.com/feed/",
    "Telenoche (Canal 4)": "https://www.telenoche.com.uy/rss/cultura.xml",
    "Portal 180": "https://www.180.com.uy/feed.php",
    "Brecha": "https://brecha.com.uy/feed/",
    "Caras y Caretas": "https://www.carasycaretas.com.uy/rss/cultura.xml",
    "Búsqueda": "https://www.busqueda.com.uy/rss/cultura.xml",
    "La Mañana": "https://www.lamanana.uy/feed/",
    "Semanario Voces": "https://voces.com.uy/feed/",
    "Medios Públicos (Canal 5 / Radios)": "https://mediospublicos.uy/feed/",
    "En Perspectiva (Radiomundo)": "https://enperspectiva.uy/feed/",
    "M24 Radio": "https://www.m24.com.uy/feed/",
    "Radio Universal 970": "https://universal970.com.uy/feed/",
    "El Telégrafo (Paysandú)": "https://www.eltelegrafo.com/feed/",
    "Maldonado Noticias": "https://maldonadonoticias.com/beta/feed/",
    "San José Ahora": "https://sanjoseahora.com.uy/feed/"
}

# ==========================================
# 3. FUNCIONES DE EVALUACIÓN Y LLM
# ==========================================
def matches_any(text: str, patterns: list) -> list:
    return [p.replace(r"\b", "").replace(r"\.", ".") for p in patterns if re.search(p, text, re.IGNORECASE)]

def evaluar_mencion(titulo: str, cuerpo: str):
    texto = f"{titulo} {cuerpo}".lower()

    # Nivel 1: Coincidencia directa
    m1 = matches_any(texto, KEYWORDS_L1)
    if m1:
        return True, "Nivel 1 (Directo)", m1

    # Nivel 2: Institucional/Autoridades cruzado con contexto o entidades de medios
    m2 = matches_any(texto, KEYWORDS_L2)
    ctx = matches_any(texto, KEYWORDS_CONTEXTO)
    medios = matches_any(texto, KEYWORDS_MEDIOS)
    if m2 and (ctx or medios):
        return True, "Nivel 2 (Institucional + Contexto/Medio)", m2 + ctx + medios

    # Nivel 3: Obra de cartelera vinculada al Sodre o salas
    m3 = matches_any(texto, KEYWORDS_L3)
    anclas = matches_any(texto, [r"\bsodre\b", r"\bbns\b", r"\bossodre\b", r"\btickantel\b", r"adela reta", r"sala fabini"])
    if m3 and anclas:
        return True, "Nivel 3 (Cartelera)", m3 + anclas

    return False, None, []

def obtener_enlaces_existentes():
    if not os.path.exists(CSV_PATH):
        return set()
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {fila.get("enlace", "") for fila in reader}

def clasificar_con_gemini(client: genai.Client, titulo: str, texto: str) -> Optional[AnalisisMencionSodre]:
    prompt = f"Analiza esta noticia cultural sobre el Sodre en Uruguay:\nTítulo: {titulo}\nTexto: {texto}"
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
        print(f"Error al analizar con Gemini: {e}")
        return None

# ==========================================
# 4. EJECUCIÓN PRINCIPAL
# ==========================================
def main():
    os.makedirs("data", exist_ok=True)
    enlaces_previos = obtener_enlaces_existentes()
    client = genai.Client()
    nuevas_filas = []

    columnas = [
        "fecha", "medio", "titulo", "enlace", "nivel_coincidencia",
        "elenco_o_cuerpo", "sentimiento", "tema_principal",
        "obra_mencionada", "resumen_gemini", "keywords_detectadas"
    ]

    escribir_cabecera = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0

    for medio, url in FEEDS.items():
        print(f"Escaneando feed: {medio}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                enlace = getattr(entry, "link", "")
                if not enlace or enlace in enlaces_previos:
                    continue

                titulo = getattr(entry, "title", "")
                resumen = getattr(entry, "summary", "")

                fecha = None
                if hasattr(entry, "published"):
                    fecha = parser.parse(entry.published)
                elif hasattr(entry, "updated"):
                    fecha = parser.parse(entry.updated)

                if fecha and fecha.year != ANO_OBJETIVO:
                    continue

                es_relevante, nivel, matches = evaluar_mencion(titulo, resumen)
                if es_relevante:
                    print(f"  -> Coincidencia: '{titulo[:50]}...' Analizando con Gemini...")
                    analisis = clasificar_con_gemini(client, titulo, resumen)

                    fila = {
                        "fecha": fecha.strftime("%Y-%m-%d %H:%M") if fecha else "S/F",
                        "medio": medio,
                        "titulo": titulo.replace("\n", " ").strip(),
                        "enlace": enlace,
                        "nivel_coincidencia": nivel,
                        "elenco_o_cuerpo": analisis.elenco_o_cuerpo if analisis else "No analizado",
                        "sentimiento": analisis.sentimiento if analisis else "No analizado",
                        "tema_principal": analisis.tema_principal if analisis else "No analizado",
                        "obra_mencionada": analisis.obra_mencionada if (analisis and analisis.obra_mencionada) else "-",
                        "resumen_gemini": (analisis.resumen_ejecutivo if analisis else resumen[:200]).replace("\n", " "),
                        "keywords_detectadas": ", ".join(matches)
                    }
                    nuevas_filas.append(fila)
                    enlaces_previos.add(enlace)
        except Exception as e:
            print(f"Error procesando {medio}: {e}")

    if nuevas_filas:
        with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            if escribir_cabecera:
                writer.writeheader()
            for r in nuevas_filas:
                writer.writerow(r)
        print(f"\nÉxito: Se indexaron y guardaron {len(nuevas_filas)} menciones en {CSV_PATH}.")
    else:
        print("\nNo se encontraron noticias nuevas en esta ejecución.")

if __name__ == "__main__":
    main()
