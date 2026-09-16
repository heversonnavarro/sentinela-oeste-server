"""
SENTINELA OESTE — Coletor/Orquestrador v0.5
Coleta Open-Meteo automaticamente, recebe alertas oficiais normalizados,
executa o rastreador v0.3 e o motor de risco v0.4.
"""
import json, subprocess, sys, urllib.request
from pathlib import Path

BASE=Path(__file__).parent
CITIES=[
 ("Foz do Iguaçu",-25.5469,-54.5882),("São Miguel do Iguaçu",-25.3481,-54.2405),
 ("Medianeira",-25.2953,-54.0939),("Matelândia",-25.2408,-53.9961),
 ("Céu Azul",-25.1489,-53.8415),("Cascavel",-24.9555,-53.4552)
]

def get_json(url):
    with urllib.request.urlopen(url,timeout=20) as r:return json.load(r)

def collect_openmeteo():
    rows=[]
    for name,lat,lon in CITIES:
        u=(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=weather_code,wind_gusts_10m&timezone=America%2FSao_Paulo")
        c=get_json(u)["current"]
        rows.append({"city":name,"weather_code":c.get("weather_code",0),
                     "gust_kmh":c.get("wind_gusts_10m",0)})
    return rows

def load_official():
    # Interface estável: backend futuro pode substituir este arquivo por CAP/API.
    p=BASE/"alertas_oficiais_normalizados.json"
    if not p.exists(): return []
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    subprocess.run([sys.executable,str(BASE/"coletor_alertas_oficiais_v06.py")],cwd=BASE,check=False)
    rows=collect_openmeteo()
    context={
      "max_west_corridor_gust_kmh":max((x["gust_kmh"] for x in rows),default=0),
      "thunderstorm_signal":any(95<=int(x["weather_code"])<=99 for x in rows),
      "hail_signal":False,
      "official_alerts":load_official(),
      "open_meteo_points":rows
    }
    (BASE/"contexto_v04.json").write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding="utf-8")
    subprocess.run([sys.executable,str(BASE/"sentinela_motor_v03.py")],cwd=BASE,check=True)
    subprocess.run([sys.executable,str(BASE/"sentinela_risco_v04.py")],cwd=BASE,check=True)
    risk=json.loads((BASE/"sentinela_risco_v04.json").read_text(encoding="utf-8"))
    print("\n=== RESULTADO INTEGRADO ===")
    print(risk["emoji"],risk["level"],"| score",risk["score"])
    for x in risk["reasons"]:print("•",x)
if __name__=="__main__":main()
