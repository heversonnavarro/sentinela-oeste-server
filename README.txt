SENTINELA OESTE — BACKEND INTEGRADO v0.6

NOVO
• coletor automático da página pública Alertas Vigentes da Defesa Civil PR;
• normalização para a interface do Motor de Risco;
• filtro por fenômeno meteorológico + municípios do corredor Oeste;
• regra anti-falso-positivo: legenda genérica da página não vira alerta para Cascavel;
• orquestrador chama o coletor oficial antes do Open-Meteo/radar/risco.

FLUXO
Defesa Civil PR -> coletor v0.6
Open-Meteo -> coletor v0.5
RainViewer -> rastreador v0.3
Tudo -> Motor de Risco v0.4 -> sentinela_risco_v04.json

LIMITAÇÃO ATUAL
O portal público da Defesa Civil é adequado para consulta humana, mas o protótipo ainda
não possui um feed CAP público estruturado validado para extrair automaticamente a
geometria exata de cada alerta. O INMET permanece fonte oficial externa de confirmação
até validarmos uma interface estruturada estável.

PRÓXIMO / ÚLTIMO BLOCO DO PROTÓTIPO
Servidor 24h + endpoint HTTP + conexão do aplicativo Android ao resultado.
