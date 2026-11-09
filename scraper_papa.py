import feedparser
import pandas as pd
from datetime import datetime
import os

# Términos de búsqueda exhaustivos para la visita papal y el Sodre
QUERIES = [
    "Papa León XIV Sodre",
    "León XIV Uruguay Sodre",
    "Vaticano Sodre Montevideo",
    "Orquesta Juvenil Sodre Papa",
    "Coro Nacional Sodre León XIV"
]

def buscar_menciones_papa():
    menciones = []
    for q in QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=es-AR&gl=AR&ceid=AR:es"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            menciones.append({
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "medio": entry.get("source", {}).get("title", "Desconocido"),
                "titulo": entry.title,
                "enlace": entry.link,
                "tema": "Visita Papal y Sodre"
            })
            
    df = pd.DataFrame(menciones)
    if not df.empty:
        df = df.drop_duplicates(subset=["enlace"])
    return df

if __name__ == "__main__":
    archivo_csv = "data/menciones_papa_2026.csv"
    
    # Cargar histórico si existe o crear nuevo
    if os.path.exists(archivo_csv):
        df_existente = pd.read_csv(archivo_csv)
    else:
        df_existente = pd.DataFrame(columns=["fecha", "medio", "titulo", "enlace", "tema"])
        
    df_nuevos = buscar_menciones_papa()
    
    if not df_nuevos.empty:
        df_final = pd.concat([df_existente, df_nuevos]).drop_duplicates(subset=["enlace"])
        df_final.to_csv(archivo_csv, index=False)
        print(f"Actualizado: {len(df_nuevos)} notas nuevas del Papa agregadas.")
    else:
        print("No se encontraron nuevas menciones.")
