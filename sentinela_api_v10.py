"""
SENTINELA OESTE 1.0 EXPERIMENTAL — API local
Executa o pipeline periodicamente e expõe /status para o aplicativo.
Somente biblioteca padrão + dependências já usadas pelo motor.
"""
import json, subprocess, sys, threading, time, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE=Path(__file__).parent
RESULT=BASE/"sentinela_risco_v04.json"
INTERVAL=600  # 10 min

def run_pipeline():
    while True:
        try:
            subprocess.run([sys.executable,str(BASE/"sentinela_orquestrador_v05.py")],
                           cwd=BASE,timeout=180,check=False)
        except Exception as e:
            print("Pipeline:",e)
        time.sleep(INTERVAL)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/")!="/status":
            self.send_response(404);self.end_headers();return
        try:
            data=json.loads(RESULT.read_text(encoding="utf-8")) if RESULT.exists() else {
              "version":"1.0-exp","level":"INICIALIZANDO","emoji":"⚪","score":0,
              "reasons":["Pipeline ainda não concluiu a primeira análise."]
            }
            body=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(200);self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(body)))
            self.end_headers();self.wfile.write(body)
        except Exception as e:
            self.send_response(500);self.end_headers();self.wfile.write(str(e).encode())
    def log_message(self,fmt,*args): pass

if __name__=="__main__":
    threading.Thread(target=run_pipeline,daemon=True).start()
    port=int(os.environ.get("PORT","10000"))
    print(f"Sentinela API ouvindo em 0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
