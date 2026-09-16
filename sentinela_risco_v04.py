"""
SENTINELA OESTE — Motor de Risco v0.4
Combina a saída do rastreador v0.3 com sinais meteorológicos e alertas oficiais
normalizados. Regras deliberadamente auditáveis/conservadoras.

Entrada:
- sentinela_resultado_v03.json
- contexto_v04.json (Open-Meteo + alertas oficiais já coletados/normalizados)

Saída:
- sentinela_risco_v04.json

IMPORTANTE: este protótipo NÃO interpreta CAP bruto ainda; espera alertas normalizados.
"""
import json, math, os, sys
from datetime import datetime, timezone

TRACK="sentinela_resultado_v03.json"
CTX="contexto_v04.json"
OUT="sentinela_risco_v04.json"

def clamp(x,a=0,b=100): return max(a,min(b,x))

def cell_score(c):
    score=0; reasons=[]
    conf=c.get("confidence",0); dist=c.get("distance_cascavel_km",999)
    speed=c.get("speed_kmh",0); trend=c.get("trend_percent",0)
    intercept=c.get("intercepts_protection_zone",False)

    if intercept:
        score+=30; reasons.append("trajetória experimental intercepta zona de proteção")
    if conf>=75:
        score+=20; reasons.append("rastreamento com confiança alta")
    elif conf>=50:
        score+=12; reasons.append("rastreamento com confiança moderada")
    if dist<=80:
        score+=18; reasons.append("célula a até 80 km de Cascavel")
    elif dist<=150:
        score+=10; reasons.append("célula a até 150 km de Cascavel")
    if trend>=25:
        score+=12; reasons.append("eco em intensificação")
    elif trend>=10:
        score+=6; reasons.append("eco com tendência de aumento")
    if 20<=speed<=100:
        score+=5
    return clamp(score),reasons

def official_score(alerts):
    score=0; reasons=[]; strongest=0
    sevmap={"extreme":4,"severe":3,"moderate":2,"minor":1,"unknown":0}
    for a in alerts:
        if not a.get("relevant_to_cascavel_or_west",False): continue
        sev=sevmap.get(str(a.get("severity","unknown")).lower(),0)
        strongest=max(strongest,sev)
        if sev>=4: score=max(score,45);reasons.append("alerta oficial EXTREMO relevante")
        elif sev==3: score=max(score,35);reasons.append("alerta oficial SEVERO relevante")
        elif sev==2: score=max(score,18);reasons.append("alerta oficial MODERADO relevante")
    return score,reasons,strongest

def meteo_score(ctx):
    score=0;reasons=[]
    gust=float(ctx.get("max_west_corridor_gust_kmh",0) or 0)
    storm=bool(ctx.get("thunderstorm_signal",False))
    hail=bool(ctx.get("hail_signal",False))
    if gust>=90: score+=25;reasons.append(f"rajada modelada/observada muito forte ({gust:.0f} km/h)")
    elif gust>=70: score+=16;reasons.append(f"rajada forte ({gust:.0f} km/h)")
    elif gust>=50: score+=8;reasons.append(f"rajada relevante ({gust:.0f} km/h)")
    if storm: score+=10;reasons.append("sinal de tempestade no corredor")
    if hail: score+=12;reasons.append("sinal de granizo")
    return clamp(score,0,35),reasons

def classify(track,ctx):
    cells=track.get("cells",[])
    ranked=[]
    for c in cells:
        s,r=cell_score(c); ranked.append((s,c,r))
    ranked.sort(key=lambda x:x[0],reverse=True)
    cs,cell,cr=(ranked[0] if ranked else (0,None,[]))
    oscore,orr,strongest=official_score(ctx.get("official_alerts",[]))
    mscore,mr=meteo_score(ctx)

    total=clamp(cs+oscore+mscore)
    # Gates: trajetória sozinha não deve elevar uma célula enfraquecendo a LARANJA.
    independent_strong=(strongest>=3)
    trend=(cell.get("trend_percent",0) if cell else 0)
    radar_strong=bool(cell and cell.get("intercepts_protection_zone") and
                      cell.get("confidence",0)>=75 and trend>=-10)
    radar_preparation=bool(cell and cell.get("intercepts_protection_zone") and
                           cell.get("confidence",0)>=50 and trend>=-10)

    if total>=75 and radar_strong and independent_strong:
        level="VERMELHO";emoji="🔴"
    elif total>=50 and (radar_strong or strongest>=3):
        level="LARANJA";emoji="🟠"
    elif total>=25:
        level="AMARELO";emoji="🟡"
    else:
        level="VERDE";emoji="🟢"

    # Casa de madeira: preparação antecipada só se o eco não estiver enfraquecendo claramente.
    if level=="AMARELO" and total>=42 and radar_preparation:
        level="LARANJA";emoji="🟠"
        cr.append("limiar de preparação conservador para residência de madeira")
    elif level=="AMARELO" and cell and cell.get("intercepts_protection_zone") and trend < -10:
        cr.append("eco em enfraquecimento: mantido em observação, sem elevar preparação")

    return {
      "version":"0.4","generated_utc":datetime.now(timezone.utc).isoformat(),
      "level":level,"emoji":emoji,"score":round(total),
      "radar_cell_score":round(cs),"official_score":round(oscore),"meteo_score":round(mscore),
      "red_gate":{"radar_strong":radar_strong,"independent_official_strong":independent_strong},
      "primary_cell":cell,
      "reasons":list(dict.fromkeys(cr+orr+mr)),
      "disclaimer":"Protótipo experimental; não substitui Defesa Civil, INMET ou Simepar."
    }

def main():
    if not os.path.exists(TRACK):
        print(f"Falta {TRACK}. Execute primeiro o Motor v0.3.");sys.exit(2)
    if not os.path.exists(CTX):
        sample={
          "max_west_corridor_gust_kmh":0,
          "thunderstorm_signal":False,
          "hail_signal":False,
          "official_alerts":[
            {"source":"Defesa Civil PR ou INMET","severity":"unknown",
             "relevant_to_cascavel_or_west":False,"headline":""}
          ]
        }
        with open("contexto_v04_EXEMPLO.json","w",encoding="utf-8") as f:json.dump(sample,f,ensure_ascii=False,indent=2)
        print("Falta contexto_v04.json. Criei contexto_v04_EXEMPLO.json.");sys.exit(2)
    with open(TRACK,encoding="utf-8") as f:track=json.load(f)
    with open(CTX,encoding="utf-8") as f:ctx=json.load(f)
    result=classify(track,ctx)
    with open(OUT,"w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(f"{result['emoji']} SENTINELA OESTE — {result['level']} | score {result['score']}/100")
    for r in result["reasons"]: print("•",r)
    print("Gate vermelho:",result["red_gate"])
    print("Saída:",OUT)
if __name__=="__main__":main()
