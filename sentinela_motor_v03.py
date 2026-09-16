"""
SENTINELA OESTE — Motor de Rastreamento v0.3
Protótipo experimental.

Evoluções:
- segmenta múltiplos ecos/células;
- acompanha trilhas em vários quadros, não só no último par;
- rejeita saltos/velocidades implausíveis;
- mede consistência de direção e velocidade;
- calcula confiança do rastreamento;
- projeta aproximação à zona de Cascavel;
- gera saída estruturada JSON para futura integração com o app/backend.

NÃO é previsão oficial nem detector de tornado.
"""
import io,json,math,urllib.request,statistics
from PIL import Image
from collections import deque

API="https://api.rainviewer.com/public/weather-maps.json"
CENTER=(-25.15,-54.35); CASCAVEL=(-24.9555,-53.4552)
ZOOM=7; SIZE=512; COLOR=2; OPTIONS="0_0"
MIN_PIXELS=25
MAX_MATCH_KM=65.0
MAX_SPEED_KMH=140.0
MIN_SPEED_FOR_PROJECTION=5.0
PROTECT_RADIUS_KM=35.0
MAX_PROJECTION_HOURS=3.0

def get_json(url):
    with urllib.request.urlopen(url,timeout=20) as r:return json.load(r)
def get_image(url):
    with urllib.request.urlopen(url,timeout=30) as r:return Image.open(io.BytesIO(r.read())).convert("RGBA")
def hav(a,b):
    R=6371.;p1,p2=map(math.radians,(a[0],b[0]));dp=math.radians(b[0]-a[0]);dl=math.radians(b[1]-a[1])
    q=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(q))
def px_latlon(px,py):
    n=2**ZOOM;lat,lon=CENTER;x0=(lon+180)/360*n*256
    y0=(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n*256
    x=x0+(px-SIZE/2)*(256/SIZE);y=y0+(py-SIZE/2)*(256/SIZE)
    lon2=x/(n*256)*360-180
    lat2=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/(n*256)))))
    return lat2,lon2
def echo_pixel(r,g,b,a):
    return a>50 and max(r,g,b)>85 and max(r,g,b)-min(r,g,b)>20

def segment(im):
    step=2;gw,gh=im.width//step,im.height//step
    mask=[[False]*gw for _ in range(gh)];wt=[[0.0]*gw for _ in range(gh)]
    for y in range(gh):
        for x in range(gw):
            r,g,b,a=im.getpixel((x*step,y*step))
            if echo_pixel(r,g,b,a):
                mask[y][x]=True;wt[y][x]=(max(r,g,b)/255.)*(a/255.)
    seen=set();out=[]
    for sy in range(gh):
        for sx in range(gw):
            if not mask[sy][sx] or (sx,sy) in seen:continue
            q=deque([(sx,sy)]);seen.add((sx,sy));pts=[]
            while q:
                x,y=q.popleft();pts.append((x,y,wt[y][x]))
                for dy in (-1,0,1):
                    for dx in (-1,0,1):
                        if dx==0 and dy==0:continue
                        nx,ny=x+dx,y+dy
                        if 0<=nx<gw and 0<=ny<gh and mask[ny][nx] and (nx,ny) not in seen:
                            seen.add((nx,ny));q.append((nx,ny))
            if len(pts)<MIN_PIXELS:continue
            sw=sum(p[2] for p in pts)
            cx=sum(p[0]*step*p[2] for p in pts)/sw;cy=sum(p[1]*step*p[2] for p in pts)/sw
            la,lo=px_latlon(cx,cy)
            out.append({"lat":la,"lon":lo,"pixels":len(pts),"mass":sw})
    return sorted(out,key=lambda c:c["mass"],reverse=True)

def bearing(a,b):
    p1,p2=map(math.radians,(a[0],b[0]));dl=math.radians(b[1]-a[1])
    y=math.sin(dl)*math.cos(p2);x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360
def direction(v):return ["N","NE","L","SE","S","SO","O","NO"][int((v+22.5)//45)%8]
def angle_diff(a,b):return abs((a-b+180)%360-180)

def build_tracks(series):
    tracks=[];next_id=1
    for ti,(ts,cells) in enumerate(series):
        if ti==0:
            for c in cells:
                tracks.append({"id":next_id,"points":[dict(c,time=ts)]});next_id+=1
            continue
        prev_ts=series[ti-1][0];dt=(ts-prev_ts)/3600
        active=[t for t in tracks if t["points"][-1]["time"]==prev_ts]
        candidates=[]
        for t in active:
            p=t["points"][-1]
            for ci,c in enumerate(cells):
                d=hav((p["lat"],p["lon"]),(c["lat"],c["lon"]))
                speed=d/dt if dt>0 else 9999
                if d<=MAX_MATCH_KM and speed<=MAX_SPEED_KMH:
                    # Penalize dramatic mass changes but do not forbid them.
                    ratio=max(c["mass"],p["mass"])/max(min(c["mass"],p["mass"]),1e-6)
                    score=d + min(30,(ratio-1)*8)
                    candidates.append((score,t,ci,c))
        used_tracks=set();used_cells=set()
        for _,t,ci,c in sorted(candidates,key=lambda x:x[0]):
            if t["id"] in used_tracks or ci in used_cells:continue
            t["points"].append(dict(c,time=ts));used_tracks.add(t["id"]);used_cells.add(ci)
        for ci,c in enumerate(cells):
            if ci not in used_cells:
                tracks.append({"id":next_id,"points":[dict(c,time=ts)]});next_id+=1
    return tracks

def track_metrics(t):
    pts=t["points"];speeds=[];dirs=[]
    for a,b in zip(pts,pts[1:]):
        hours=(b["time"]-a["time"])/3600
        if hours<=0:continue
        d=hav((a["lat"],a["lon"]),(b["lat"],b["lon"]))
        speeds.append(d/hours);dirs.append(bearing((a["lat"],a["lon"]),(b["lat"],b["lon"])))
    if not speeds:return None
    speed=statistics.median(speeds)
    # Circular mean
    sx=sum(math.sin(math.radians(x)) for x in dirs);cx=sum(math.cos(math.radians(x)) for x in dirs)
    br=(math.degrees(math.atan2(sx,cx))+360)%360
    dir_dev=sum(angle_diff(x,br) for x in dirs)/len(dirs)
    speed_cv=(statistics.pstdev(speeds)/max(statistics.mean(speeds),1))*100 if len(speeds)>1 else 45
    n=len(pts)
    # Confidence 0-100: persistence + directional/speed consistency.
    persistence=min(45,n*9)
    direction_score=max(0,30-dir_dev*0.5)
    speed_score=max(0,25-speed_cv*0.35)
    conf=round(max(0,min(100,persistence+direction_score+speed_score)))
    trend=(pts[-1]["mass"]/pts[0]["mass"]-1)*100 if pts[0]["mass"] else 0
    return speed,br,dir_dev,speed_cv,conf,trend

def step_point(start,br_deg,d):
    R=6371.;br=math.radians(br_deg);delta=d/R;p1=math.radians(start[0]);l1=math.radians(start[1])
    p2=math.asin(math.sin(p1)*math.cos(delta)+math.cos(p1)*math.sin(delta)*math.cos(br))
    l2=l1+math.atan2(math.sin(br)*math.sin(delta)*math.cos(p1),math.cos(delta)-math.sin(p1)*math.sin(p2))
    return math.degrees(p2),math.degrees(l2)

def project(start,br,speed):
    best=hav(start,CASCAVEL);best_t=0
    for mins in range(10,int(MAX_PROJECTION_HOURS*60)+1,10):
        pos=step_point(start,br,speed*mins/60);d=hav(pos,CASCAVEL)
        if d<best:best,best_t=d,mins
    return best,best_t

def confidence_label(v):
    return "alta" if v>=75 else "moderada" if v>=50 else "baixa"

def main():
    meta=get_json(API);frames=meta["radar"]["past"][-7:];series=[]
    for f in frames:
        url=f'{meta["host"]}{f["path"]}/{SIZE}/{ZOOM}/{CENTER[0]}/{CENTER[1]}/{COLOR}/{OPTIONS}.png'
        series.append((f["time"],segment(get_image(url))))
    tracks=build_tracks(series)
    latest=series[-1][0];results=[]
    for t in tracks:
        if t["points"][-1]["time"]!=latest or len(t["points"])<2:continue
        m=track_metrics(t)
        if not m:continue
        speed,br,dd,scv,conf,trend=m;p=t["points"][-1]
        dc=hav((p["lat"],p["lon"]),CASCAVEL)
        closest,eta=project((p["lat"],p["lon"]),br,speed)
        intercept=conf>=50 and speed>=MIN_SPEED_FOR_PROJECTION and closest<=PROTECT_RADIUS_KM
        results.append({
          "cell_id":t["id"],"frames_tracked":len(t["points"]),
          "lat":round(p["lat"],4),"lon":round(p["lon"],4),
          "distance_cascavel_km":round(dc),
          "direction_deg":round(br),"direction":direction(br),
          "speed_kmh":round(speed),"trend_percent":round(trend),
          "confidence":conf,"confidence_label":confidence_label(conf),
          "projected_min_distance_km":round(closest),"eta_closest_min":eta,
          "intercepts_protection_zone":intercept
        })
    results.sort(key=lambda r:(not r["intercepts_protection_zone"],-r["confidence"],r["distance_cascavel_km"]))
    print("SENTINELA OESTE — MOTOR v0.3")
    print(f"Quadros analisados: {len(series)} | trilhas ativas avaliadas: {len(results)}")
    for r in results[:10]:
        print(f"\nCÉLULA {r['cell_id']} • {r['frames_tracked']} quadros • confiança {r['confidence_label']} ({r['confidence']}%)")
        print(f" distância: {r['distance_cascavel_km']} km | movimento {r['direction']} {r['speed_kmh']} km/h")
        print(f" tendência visual: {r['trend_percent']:+d}%")
        print(f" projeção: {'INTERCEPTA' if r['intercepts_protection_zone'] else 'não confirma interceptação'} zona de Cascavel")
        if r["eta_closest_min"]:print(f" maior aproximação linear ~{r['eta_closest_min']} min | ~{r['projected_min_distance_km']} km")
    with open("sentinela_resultado_v03.json","w",encoding="utf-8") as f:
        json.dump({"version":"0.3","protection_radius_km":PROTECT_RADIUS_KM,"cells":results},f,ensure_ascii=False,indent=2)
    print("\nResultado estruturado salvo em sentinela_resultado_v03.json")
    print("V0.3 ainda é experimental: radar pode conter fusão/divisão/nascimento de células.")
if __name__=="__main__":main()
