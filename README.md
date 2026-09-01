# Carrossel mensal — Bolsas em dólar (G20+) e Moedas frente ao dólar

Pipeline mensal: **yfinance → JSON → HTML → Playwright → JPEG → Instagram
Graph API**, orquestrado por GitHub Actions (mesmo modelo do fechamento
diário).

## Fluxo

```
coleta_dados.py   → output/dados.json + composicao_log.csv (auditoria)
render_cards.py   → output/cards/{bolsas,moedas}_{mes,12m}.jpg
publicar_instagram.py → 2 carrosséis (mês encerrado e 12 meses)
```

Roda todo **dia 1 às 09:30 (Brasília)**, calculando o mês-calendário que
acabou de encerrar. Também dá para disparar manualmente (workflow_dispatch),
inclusive escolhendo publicar só um dos carrosséis ou nenhum (`nao` = só
gera as imagens, útil para conferir antes).

## Lógica de composição (para sua checagem de sanidade)

```
retorno_usd = (1 + retorno_indice_local) × (1 + var_moeda_vs_usd) − 1
var_moeda_vs_usd = taxa_inicio / taxa_fim − 1   (Yahoo cota XXX por USD)
```

Cada linha calculada sai em `output/composicao_log.csv` com ticker usado,
datas efetivas dos pregões e as três pernas (r_local, r_fx, r_usd). Para
conferir o Real: compare r_fx do BRL no log com a variação que você calcular
manualmente do USDBRL invertido.

## Composição das listas (editável em `coleta_dados.py`)

- G20 + Taiwan e Hong Kong (como no modelo de referência).
- Zona do Euro representada por **Stoxx 50 + Euro** (cobre DE/FR/IT);
  **Suíça (SMI + CHF)** incluída como diferencial.
- **Sem MOEX nem Tadawul** nas bolsas (cobertura do Yahoo não confiável);
  o **rublo** está nas moedas, com ressalva de liquidez offshore.
- **Riyal saudita fora** das moedas (peg ao dólar ⇒ sempre ~0%).
- **Dólar de Singapura** incluído (estava no modelo de referência).

## Fragilidades conhecidas (leia antes do primeiro run real)

1. **Merval em dólar**: o câmbio ARS=X do Yahoo é o oficial. Quando há spread
   relevante para o CCL/blue, o Merval em USD sai **superestimado**. Se quiser
   rigor, a alternativa é calcular o dólar CCL via ADR (ex.: GGAL vs GGAL.BA)
   — posso implementar depois.
2. **JSE Top 40 (África do Sul)**: cobertura irregular no Yahoo. O script tem
   fallback de tickers e, se nenhum responder, remove a linha e registra em
   `output/avisos.txt` (o workflow mostra como warning). Confira no primeiro
   run.
3. **Feriados assíncronos**: cada bolsa fecha o mês num pregão diferente. O
   script usa o último fechamento disponível ≤ data-limite, por série. Isso é
   o padrão de mercado, mas gera descasamentos de 1–2 dias entre países.
4. **Rate limit do Yahoo**: o download é em lote (1 request multiticker).
   Se falhar, rode o workflow de novo manualmente.
5. **Checagens de sanidade**: variação mensal em USD acima de ±60% (ou ±300%
   em 12m) gera warning no log do Actions — não bloqueia, mas confira.

## Setup

1. Repositório **público** (necessário para servir os JPEGs à Graph API via
   raw.githubusercontent.com — ver alternativas no SETUP_META.md).
2. Copie a estrutura deste pacote para a raiz do repo (o workflow precisa
   estar em `.github/workflows/`).
3. Siga o `SETUP_META.md` para criar os Secrets `IG_USER_ID` e
   `IG_ACCESS_TOKEN`.
4. (Opcional) Os secrets `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` que você já usa
   habilitam o backup por Telegram automaticamente.
5. Primeiro teste: rode o workflow manualmente com `publicar = nao`, baixe o
   artifact e confira imagens + `composicao_log.csv` antes de ligar a
   publicação.

## Teste local sem rede

```
python scripts/coleta_dados.py --mock   # dados sintéticos
python scripts/render_cards.py          # requer playwright + chromium
```
