import feedparser
import pandas as pd
from datetime import datetime
import os

# Términos específicos para agencias internacionales, encuentro con Orsi y Sodre
QUERIES = [
    "Papa Uruguay Reuters",
    "Papa Uruguay AP Associated Press",
    "Papa Uruguay AFP",
    "Papa Uruguay EFE",
    "León XIV Yamandú Orsi",
    "Sodre Papa Uruguay",
    "Orquesta Sodre Vaticano",
    "Coro Sodre León XIV",
    "Pope Uruguay Sodre Choir",
    "Vatican News Uruguay Sodre"
]

def buscar_menciones_internacionales():
    menciones = []
    for q in QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={q.replace(' ', '+')}&hl=es-AR&gl=AR&ceid=AR:es"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            titulo_lower = entry.title.lower()
            # Filtramos para asegurar relevancia institucional o internacional
            if any(term in titulo_lower for term in ['papa', 'león', 'leon', 'vaticano', 'orsi', 'sodre', 'efe', 'reuters', 'ap', 'afp', 'choir', 'orchestra']):
                menciones.append({
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "medio": entry.get("source", {}).get("title", "Agencia Internacional / Prensa"),
                    "titulo": entry.title,
                    "enlace": entry.link,
                    "nivel_coincidencia": "Agencia / Internacional",
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
        
    df_nuevos = buscar_menciones_internacionales()
    
    if not df_nuevos.empty:
        df_final = pd.concat([df_existente, df_nuevos]).drop_duplicates(subset=["enlace"])
        df_final.to_csv(archivo_csv, index=False)
        print(f"Éxito: {len(df_nuevos)} notas internacionales incorporadas.")
    else:
        print("Sin nuevas menciones en esta ejecución.")
