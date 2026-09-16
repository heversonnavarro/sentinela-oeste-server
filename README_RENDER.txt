SENTINELA OESTE — PACOTE PARA RENDER

Este pacote já está ajustado para:
- bind em 0.0.0.0
- porta fornecida pela variável PORT do Render
- build: pip install -r requirements.txt
- start: python sentinela_api_v10.py
- health check: /status

PASSOS:
1. Criar repositório GitHub chamado sentinela-oeste-server.
2. Enviar TODOS os arquivos desta pasta para a raiz do repositório.
3. No Render: New > Web Service > conectar GitHub > selecionar repositório.
4. Se o render.yaml for reconhecido via Blueprint, usar a configuração dele.
   Caso configure manualmente:
   Build Command: pip install -r requirements.txt
   Start Command: python sentinela_api_v10.py
   Instance Type: Free
5. Após deploy, testar https://SEU-NOME.onrender.com/status

ATENÇÃO:
O plano Free dorme após 15 min sem tráfego de entrada. Ao acordar pode levar ~1 min.
Isso é aceitável para teste, não para alerta crítico definitivo.
