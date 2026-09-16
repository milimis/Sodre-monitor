import csv
import os
import pandas as pd

EXCEL_PATH = "data/menciones_sodre_prensa_2025.xlsx"
CSV_PATH = "data/menciones_sodre_2025.csv"

def clasificar_mencion(titulo, medio):
    t = (str(titulo) + " " + str(medio)).lower()
    
    # Elenco o cuerpo
    elenco = "Institucional / Autoridades / Varios"
    if any(k in t for k in ["ballet", "bns", "bailarín", "bailarina", "coreograf", "coppélia", "cascanueces", "giselle", "la bayadera", "romeo y julieta", "carmina burana"]):
        elenco = "Ballet Nacional (BNS)"
    elif any(k in t for k in ["ossodre", "orquesta sinfónica", "filarmónica", "sinfónica del sodre", "director titular"]):
        elenco = "Orquesta Sinfónica (OSSODRE)"
    elif any(k in t for k in ["coro de niños", "coro infantil", "coro juvenil"]):
        elenco = "Coro de Niños / Juvenil"
    elif any(k in t for k in ["coro nacional", "coro del sodre", "coro"]):
        elenco = "Coro Nacional"
    elif any(k in t for k in ["orquesta juvenil", "sistema de orquestas", "juvenil"]):
        elenco = "Orquesta Juvenil"
    elif any(k in t for k in ["cámara", "conjunto de cámara", "cuarteto"]):
        elenco = "Conjunto de Cámara"
    elif any(k in t for k in ["lírica", "ópera", "soprano", "tenor", "barítono", "elíxir", "traviata", "madama butterfly", "maría josé siri"]):
        elenco = "Área Lírica / Ópera"
    elif any(k in t for k in ["enfas", "escuela", "formación artística", "estudiantes", "audiciones"]):
        elenco = "Escuelas de Formación (ENFAS)"
    
    # Sentimiento
    sentimiento = "neutro"
    if any(k in t for k in ["éxito", "ovación", "premio", "festeja", "celebr", "estrena", "brilla", "aplauso", "gira exitosa", "solidar", "beneficio", "destaca"]):
        sentimiento = "positivo"
    elif any(k in t for k in ["conflicto", "paro", "denuncia", "queja", "polémica", "suspenden", "reclamo", "crisis", "fallec", "murió", "renuncia"]):
        sentimiento = "negativo"

    # Tema principal
    if any(k in t for k in ["estreno", "estrena", "temporada", "presenta", "cartelera", "entradas", "función", "gira", "concierto"]):
        tema = "Cartelera y venta de entradas"
    elif any(k in t for k in ["crítica", "reseña", "opinión", "aplausos", "ovacionada"]):
        tema = "Crítica artística o reseña"
    elif any(k in t for k in ["entrevista", "mano a mano", "conversamos con", "en diálogo con"]):
        tema = "Entrevista a artistas o autoridades"
    elif any(k in t for k in ["presupuesto", "gestión", "quinquenio", "plan estratégico", "autoridades", "asume", "designación"]):
        tema = "Gestión cultural y presupuesto"
    else:
        tema = "Novedades institucionales o autoridades"

    # Obra
    obra = "-"
    obras_conocidas = [
        "Carmina Burana", "Coppélia", "El Corsario", "Cascanueces", "Giselle", "La Bayadere", "La Sylphide",
        "Don Quijote", "Star Wars", "Beatles + Bach", "Elíxir de Amor", "La Traviata", "Madama Butterfly",
        "La Bella Durmiente", "Romeo y Julieta", "Réquiem", "Sinfonía"
    ]
    for o in obras_conocidas:
        if o.lower() in t:
            obra = o
            break

    keywords = []
    if "sodre" in t: keywords.append("sodre")
    if "ballet" in t or "bns" in t: keywords.append("ballet nacional")
    if "ossodre" in t or "sinfónica" in t: keywords.append("ossodre")
    if "coro" in t: keywords.append("coro nacional")
    if "adela reta" in t or "auditorio nacional" in t: keywords.append("auditorio adela reta")
    if not keywords: keywords.append("prensa sodre")

    return elenco, sentimiento, tema, obra, f"Mención en {medio} sobre {titulo[:100]}.", ", ".join(keywords)

def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"No se encontró {EXCEL_PATH}")
        return

    df = pd.read_excel(EXCEL_PATH, sheet_name=0)
    filas = []

    for _, row in df.iterrows():
        f_date = str(row['Fecha'])[:10]
        medio = str(row['Medio']).strip()
        titulo = str(row['Título']).strip().replace("\n", " ")
        link = str(row['Link']).strip()
        
        elenco, sent, tema, obra, resumen, kw = clasificar_mencion(titulo, medio)
        
        filas.append({
            "fecha": f"{f_date} 12:00",
            "medio": medio,
            "titulo": titulo,
            "enlace": link,
            "nivel_coincidencia": "Relevamiento Prensa Sodre 2025",
            "elenco_o_cuerpo": elenco,
            "sentimiento": sent,
            "tema_principal": tema,
            "obra_mencionada": obra,
            "resumen_gemini": resumen,
            "keywords_detectadas": kw
        })

    columnas = [
        "fecha", "medio", "titulo", "enlace", "nivel_coincidencia",
        "elenco_o_cuerpo", "sentimiento", "tema_principal",
        "obra_mencionada", "resumen_gemini", "keywords_detectadas"
    ]

    with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        for r in filas:
            writer.writerow(r)

    print(f"¡Éxito total! Se procesaron {len(filas)} filas y se guardaron en {CSV_PATH}.")

if __name__ == "__main__":
    main()
