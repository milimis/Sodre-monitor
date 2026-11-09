import feedparser
import pandas as pd
from datetime import datetime
import os

QUERIES = [
    "Papa Uruguay",
    "León XIV",
    "Vaticano Montevideo",
    "Sodre",
    "Orquesta Sodre",
    "Coro Sodre",
    "Visita Papal",
    "Pope Leo XIV Uruguay",
    "Sodre Choir Vatican"
]

def buscar_y_acumular():
    nuevas_menciones = []
    for q in QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=es-AR&gl=AR&ceid=AR:es"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            titulo = entry.title
            enlace = entry.link
            medio = entry.get("source", {}).get("title", "Medio de Prensa")
            
            nuevas_menciones.append({
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "medio": medio,
                "titulo": titulo,
                "enlace": enlace,
                "nivel_coincidencia": "Automático",
                "elenco_o_cuerpo": "Sodre / Protocolar",
                "sentimiento": "Positivo",
                "tema_principal": "Visita Papal"
            })
            
    df_nuevas = pd.DataFrame(nuevas_menciones)
    
    archivo_csv = "data/menciones_papa_2026.csv"
    os.makedirs("data", exist_ok=True)
    
    # Si ya existía el archivo, lo leemos para no perder lo anterior
    if os.path.exists(archivo_csv):
        try:
            df_viejo = pd.read_csv(archivo_csv)
            df_final = pd.concat([df_viejo, df_nuevas]).drop_duplicates(subset=["enlace"])
        except Exception:
            df_final = df_nuevas
    else:
        df_final = df_nuevas
        
    df_final.to_csv(archivo_csv, index=False)
    print(f"Total de notas acumuladas en el CSV: {len(df_final)}")

if __name__ == "__main__":
    buscar_y_acumular()
