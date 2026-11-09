import feedparser
import pandas as pd
from datetime import datetime
import os

# Lista ampliada de términos para capturar cobertura local e internacional
QUERIES = [
    "Papa León XIV",
    "León XIV Uruguay",
    "Vaticano Montevideo",
    "Sodre Papa",
    "Orquesta Juvenil Sodre León XIV",
    "Coro Nacional Sodre Papa",
    "Visita Papal Uruguay",
    "Papa Francisco Uruguay",
    "EFE Papa Uruguay",
    "Vatican News Uruguay"
]

def buscar_menciones_papa():
    menciones = []
    for q in QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=es-AR&gl=AR&ceid=AR:es"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            menciones.append({
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "medio": entry.get("source", {}).get("title", "Medio Internacional / Local"),
                "titulo": entry.title,
                "enlace": entry.link,
                "nivel_coincidencia": "Revisión",
                "elenco_o_cuerpo": "Institucional",
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
        
    df_nuevos = buscar_menciones_papa()
    
    if not df_nuevos.empty:
        # Combinar con lo que ya estaba para no perder nada
        df_final = pd.concat([df_existente, df_nuevos]).drop_duplicates(subset=["enlace"])
        df_final.to_csv(archivo_csv, index=False)
        print(f"Éxito: {len(df_nuevos)} notas incorporadas.")
    else:
        print("Sin nuevas menciones en esta ejecución.")
