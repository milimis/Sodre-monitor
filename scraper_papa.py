import feedparser
import pandas as pd
from datetime import datetime
import os

# Combinación optimizada de términos en español e inglés para agencias internacionales y Sodre
QUERIES = [
    # Español - Agencias y Visita
    "Papa Uruguay Reuters",
    "Papa Uruguay AP Associated Press",
    "Papa Uruguay AFP",
    "Papa Uruguay EFE",
    "León XIV Yamandú Orsi",
    "Sodre Papa Uruguay",
    "Orquesta Sodre Vaticano",
    "Coro Sodre León XIV",
    # Inglés - Agencias Internacionales y Cobertura Global
    "Pope Leo XIV Uruguay Reuters",
    "Pope Leo XIV Uruguay AP",
    "Pope Leo XIV Uruguay AFP",
    "Pope Leo XIV Uruguay EFE",
    "Pope Leo XIV President Orsi Uruguay",
    "Sodre Orchestra Pope Leo XIV",
    "National Choir Sodre Vatican Uruguay",
    "Uruguay Pope visit choir orchestra",
    "Vatican News Uruguay Sodre"
]

def buscar_menciones_globales():
    menciones = []
    for q in QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=es-AR&gl=AR&ceid=AR:es"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            titulo_lower = entry.title.lower()
            # Filtro inteligente para capturar menciones papales, presidenciales o artísticas del Sodre
            if any(term in titulo_lower for term in [
                'papa', 'leo', 'león', 'leon', 'vaticano', 'vatican', 'orsi', 
                'sodre', 'choir', 'orchestra', 'orquesta', 'coro', 'efe', 'reuters', 'ap', 'afp'
            ]):
                menciones.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "medio": entry.get("source", {}).get("title", "Agencia Global / Prensa"),
                    "titulo": entry.title,
                    "enlace": entry.link,
                    "nivel_coincidencia": "Global / Internacional",
                    "elenco_o_cuerpo": "Sodre / Protocolar",
                    "sentimiento": "Positivo",
                    "tema_principal": "Visita Papal y Sodre"
                })
                
    df = pd.DataFrame(menciones)
    if not df.empty:
        df = df.drop_duplicates(subset=["enlace"])
    return df

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    archivo_csv = "data/menciones_papa_2026.csv"
    
    if os.path.exists(archivo_csv):
        df_existente = pd.read_csv(archivo_csv)
    else:
        df_existente = pd.DataFrame(columns=["fecha", "medio", "titulo", "enlace", "nivel_coincidencia", "elenco_o_cuerpo", "sentimiento", "tema_principal"])
        
    df_nuevos = buscar_menciones_globales()
    
    if not df_nuevos.empty:
        df_final = pd.concat([df_existente, df_nuevos]).drop_duplicates(subset=["enlace"])
        df_final.to_csv(archivo_csv, index=False)
        print(f"Éxito: {len(df_nuevos)} notas globales incorporadas.")
    else:
        print("Sin nuevas menciones en esta ejecución.")
