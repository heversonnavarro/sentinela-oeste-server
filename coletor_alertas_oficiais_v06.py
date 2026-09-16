"""
SENTINELA OESTE — Coletor de Alertas Oficiais v0.6

Estratégia conservadora:
1) Consulta a página pública "Alertas Vigentes" da Defesa Civil PR.
2) Detecta somente alertas meteorológicos relevantes ao corredor por texto.
3) Normaliza severidade para a interface do Motor de Risco.
4) Não inventa geometria: se a página pública não expuser município/área no HTML
   obtido, o alerta não é marcado automaticamente como relevante a Cascavel.
5) INMET fica como fonte oficial de confirmação externa até termos endpoint
   estruturado estável validado no protótipo.

Dependências: apenas biblioteca padrão.
"""
import json,re,urllib.request
from html import unescape
from pathlib import Path
BASE=Path(__file__).parent
URL_DC="https://www.defesacivil.pr.gov.br/alertas-vigentes"
WEST=["cascavel","foz do iguaçu","foz do iguacu","são miguel do iguaçu","sao miguel do iguacu",
      "medianeira","matelândia","matelandia","céu azul","ceu azul"]
WEATHER=["tempest","vendaval","granizo","chuva","raio","vento","tornado"]

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"SentinelaOeste/0.6"})
    with urllib.request.urlopen(req,timeout=25) as r:return r.read().decode("utf-8","ignore")

def textify(html):
    s=re.sub(r"<script.*?</script>"," ",html,flags=re.S|re.I)
    s=re.sub(r"<style.*?</style>"," ",s,flags=re.S|re.I)
    s=re.sub(r"<[^>]+>"," ",s)
    return re.sub(r"\s+"," ",unescape(s)).strip()

def severity(txt):
    t=txt.lower()
    if "muito alta" in t or "perigo extremo" in t:return "extreme"
    if "alta" in t or "perigo significativo" in t:return "severe"
    if "moderada" in t or "atenção especial" in t or "atencao especial" in t:return "moderate"
    return "unknown"

def main():
    alerts=[]
    try:
        txt=textify(fetch(URL_DC));low=txt.lower()
        has_weather=any(k in low for k in WEATHER)
        west_hits=[x for x in WEST if x in low]
        # Página pode conter legenda sem alerta concreto; exigimos fenômeno + localidade.
        if has_weather and west_hits:
            alerts.append({
              "source":"Defesa Civil PR","severity":severity(low),
              "relevant_to_cascavel_or_west":True,
              "headline":"Alerta meteorológico público com referência ao corredor Oeste",
              "matched_locations":west_hits,"source_url":URL_DC
            })
    except Exception as e:
        alerts.append({"source":"Defesa Civil PR","severity":"unknown",
          "relevant_to_cascavel_or_west":False,"headline":"Falha de coleta: "+str(e)})
    (BASE/"alertas_oficiais_normalizados.json").write_text(
        json.dumps(alerts,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Alertas oficiais normalizados:",len(alerts))
if __name__=="__main__":main()
