#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coleta mensal — Bolsas mundiais em dólar (G20+) e Moedas frente ao dólar.

Gera output/dados.json com DOIS períodos:
  - "mes":  variação do último mês-calendário completo
  - "12m":  variação acumulada dos últimos 12 meses (fechamento do mês
            encerrado vs. mesmo fechamento 12 meses antes)

LÓGICA DE COMPOSIÇÃO (explícita, para conferência manual):
  retorno_usd = (1 + retorno_indice_moeda_local) * (1 + var_moeda_vs_usd) - 1

  onde var_moeda_vs_usd é a variação do VALOR da moeda local em dólares.
  O Yahoo cota "BRL=X" como USD/BRL (reais por dólar), então:
      valor_do_real_em_usd = 1 / (USD/BRL)
      var_moeda_vs_usd     = taxa_inicio / taxa_fim - 1

  Sanidade (exemplo): Ibovespa +5% em BRL, real caindo de 5,00 → 6,00 por
  dólar ⇒ var_fx = 5/6 - 1 = -16,67% ⇒ retorno_usd = 1,05*0,8333-1 = -12,5%.

Todo o log de composição (r_local, r_fx, r_usd, datas usadas) sai em
output/composicao_log.csv para auditoria.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DOS ATIVOS
# "tickers" é uma lista de fallback: tenta na ordem; se nenhum tiver dados,
# a linha é descartada com aviso (Rússia/África do Sul/Saudita têm cobertura
# irregular no Yahoo — por isso o mecanismo existe).
# "moeda": código ISO; None = já cotado em USD (sem perna cambial).
# ---------------------------------------------------------------------------

BOLSAS = [
    {"nome": "S&P 500",            "bandeira": "🇺🇸", "tickers": ["^GSPC"],      "moeda": None},
    {"nome": "NASDAQ",             "bandeira": "🇺🇸", "tickers": ["^IXIC"],      "moeda": None},
    {"nome": "SSE Composite (CHN)","bandeira": "🇨🇳", "tickers": ["000001.SS"],  "moeda": "CNY"},
    {"nome": "Shenzhen Index",     "bandeira": "🇨🇳", "tickers": ["399001.SZ"],  "moeda": "CNY"},
    {"nome": "Hang Seng (HKG)",    "bandeira": "🇭🇰", "tickers": ["^HSI"],       "moeda": "HKD"},
    {"nome": "TSEC Index (Taiwan)","bandeira": "🇹🇼", "tickers": ["^TWII"],      "moeda": "TWD"},
    {"nome": "Nikkei (JPN)",       "bandeira": "🇯🇵", "tickers": ["^N225"],      "moeda": "JPY"},
    {"nome": "KOSPI (KOR)",        "bandeira": "🇰🇷", "tickers": ["^KS11"],      "moeda": "KRW"},
    {"nome": "Nifty 50 (IND)",     "bandeira": "🇮🇳", "tickers": ["^NSEI"],      "moeda": "INR"},
    {"nome": "IDX Composite (IDN)","bandeira": "🇮🇩", "tickers": ["^JKSE"],      "moeda": "IDR"},
    {"nome": "ASX 200 (AUS)",      "bandeira": "🇦🇺", "tickers": ["^AXJO"],      "moeda": "AUD"},
    {"nome": "Stoxx 50 (EUR)",     "bandeira": "🇪🇺", "tickers": ["^STOXX50E"],  "moeda": "EUR"},
    {"nome": "SMI (SUI)",          "bandeira": "🇨🇭", "tickers": ["^SSMI"],      "moeda": "CHF"},
    {"nome": "FTSE 100 (UK)",      "bandeira": "🇬🇧", "tickers": ["^FTSE"],      "moeda": "GBP"},
    {"nome": "BIST 100 (TUR)",     "bandeira": "🇹🇷", "tickers": ["XU100.IS"],   "moeda": "TRY"},
    {"nome": "JSE Top 40 (ZAF)",   "bandeira": "🇿🇦", "tickers": ["^J200.JO", "STX40.JO"], "moeda": "ZAR"},
    {"nome": "TSX (CAN)",          "bandeira": "🇨🇦", "tickers": ["^GSPTSE"],    "moeda": "CAD"},
    {"nome": "IPC Mexico",         "bandeira": "🇲🇽", "tickers": ["^MXX"],       "moeda": "MXN"},
    {"nome": "Ibovespa",           "bandeira": "🇧🇷", "tickers": ["^BVSP"],      "moeda": "BRL", "destaque": True},
    # ATENÇÃO: Merval em USD pelo câmbio ARS=X (oficial) superestima o retorno
    # quando há spread p/ CCL/blue — o Yahoo não tem CCL. Mantido com ressalva.
    {"nome": "Merval (ARG)",       "bandeira": "🇦🇷", "tickers": ["^MERV"],      "moeda": "ARS"},
]

MOEDAS = [
    # código ISO → ticker Yahoo "XXX=X" = unidades de XXX por 1 USD.
    {"nome": "Euro",             "bandeira": "🇪🇺", "codigo": "EUR"},
    {"nome": "Libra",            "bandeira": "🇬🇧", "codigo": "GBP"},
    {"nome": "Franco Suíço",     "bandeira": "🇨🇭", "codigo": "CHF"},
    {"nome": "Iene Japonês",     "bandeira": "🇯🇵", "codigo": "JPY"},
    {"nome": "Yuan Chinês",      "bandeira": "🇨🇳", "codigo": "CNY"},
    {"nome": "Dólar Hong Kong",  "bandeira": "🇭🇰", "codigo": "HKD"},
    {"nome": "Dólar Taiwan",     "bandeira": "🇹🇼", "codigo": "TWD"},
    {"nome": "Won Sul-Coreano",  "bandeira": "🇰🇷", "codigo": "KRW"},
    {"nome": "Rupia Indiana",    "bandeira": "🇮🇳", "codigo": "INR"},
    {"nome": "Rupia Indonésia",  "bandeira": "🇮🇩", "codigo": "IDR"},
    {"nome": "Dólar Australiano","bandeira": "🇦🇺", "codigo": "AUD"},
    {"nome": "Dólar Singapura",  "bandeira": "🇸🇬", "codigo": "SGD"},
    {"nome": "Lira Turca",       "bandeira": "🇹🇷", "codigo": "TRY"},
    # Rublo: dados do Yahoo pós-sanções são de liquidez offshore duvidosa.
    {"nome": "Rublo Russo",      "bandeira": "🇷🇺", "codigo": "RUB"},
    {"nome": "Rand Sul-Africano","bandeira": "🇿🇦", "codigo": "ZAR"},
    {"nome": "Dólar Canadense",  "bandeira": "🇨🇦", "codigo": "CAD"},
    {"nome": "Peso Mexicano",    "bandeira": "🇲🇽", "codigo": "MXN"},
    {"nome": "Real Brasileiro",  "bandeira": "🇧🇷", "codigo": "BRL", "destaque": True},
    {"nome": "Peso Argentino",   "bandeira": "🇦🇷", "codigo": "ARS"},
]

# ---------------------------------------------------------------------------
# JANELAS DE TEMPO
# ---------------------------------------------------------------------------

def limites_periodos(hoje: date):
    """Fim = último dia do mês anterior; inícios = fim de M-2 e de M-13."""
    fim = pd.Timestamp(hoje.year, hoje.month, 1) - pd.Timedelta(days=1)
    ini_mes = pd.Timestamp(fim.year, fim.month, 1) - pd.Timedelta(days=1)
    ini_12m = (fim - pd.DateOffset(months=12)) + pd.offsets.MonthEnd(0)
    return ini_12m, ini_mes, fim


def preco_em(serie: pd.Series, limite: pd.Timestamp):
    """Último fechamento disponível em/antes de `limite` (feriados variam
    por país; usa-se o pregão mais próximo anterior)."""
    s = serie.dropna()
    s = s.loc[:limite]
    if s.empty:
        return None, None
    return float(s.iloc[-1]), s.index[-1].date()


def variacao(serie: pd.Series, ini: pd.Timestamp, fim: pd.Timestamp):
    p0, d0 = preco_em(serie, ini)
    p1, d1 = preco_em(serie, fim)
    if p0 is None or p1 is None or p0 == 0:
        return None, None, None
    return p1 / p0 - 1.0, d0, d1


# ---------------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------------

def baixar_precos(tickers, ini: pd.Timestamp, fim: pd.Timestamp) -> pd.DataFrame:
    """Baixa fechamentos diários em lote via yfinance. Isolado numa função
    para permitir mock em testes (--mock)."""
    import yfinance as yf
    df = yf.download(
        tickers,
        start=(ini - pd.Timedelta(days=15)).strftime("%Y-%m-%d"),
        end=(fim + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
        auto_adjust=False, progress=False, group_by="ticker", threads=True,
    )
    fechamentos = {}
    for t in tickers:
        try:
            serie = df[t]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
            fechamentos[t] = serie.dropna()
        except Exception:
            fechamentos[t] = pd.Series(dtype=float)
    out = pd.DataFrame(fechamentos)
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out


# ---------------------------------------------------------------------------
# CÁLCULO
# ---------------------------------------------------------------------------

def calcular(precos: pd.DataFrame, ini_12m, ini_mes, fim):
    avisos, log = [], []
    resultado = {"mes": {"bolsas": [], "moedas": []},
                 "12m": {"bolsas": [], "moedas": []}}
    janelas = {"mes": (ini_mes, fim), "12m": (ini_12m, fim)}

    def var_fx(codigo, ini, fim_):
        """Variação do valor da moeda em USD. Yahoo XXX=X = XXX por USD,
        então var = taxa_ini/taxa_fim - 1."""
        t = f"{codigo}=X"
        if t not in precos.columns or precos[t].dropna().empty:
            return None, None, None
        r, d0, d1 = variacao(precos[t], ini, fim_)
        if r is None:
            return None, None, None
        # variacao() devolve p1/p0-1 do PAR USD/XXX; inverte p/ valor da moeda:
        taxa0, _ = preco_em(precos[t], ini)
        taxa1, _ = preco_em(precos[t], fim_)
        return taxa0 / taxa1 - 1.0, d0, d1

    # --- Bolsas em USD ---
    for ativo in BOLSAS:
        serie = None
        ticker_usado = None
        for t in ativo["tickers"]:
            if t in precos.columns and not precos[t].dropna().empty:
                serie, ticker_usado = precos[t], t
                break
        if serie is None:
            avisos.append(f"[bolsas] {ativo['nome']}: sem dados em {ativo['tickers']} — linha removida.")
            continue
        for periodo, (ini, fim_) in janelas.items():
            r_local, d0, d1 = variacao(serie, ini, fim_)
            if r_local is None:
                avisos.append(f"[bolsas] {ativo['nome']} ({periodo}): janela sem preços — removido.")
                continue
            if ativo["moeda"] is None:
                r_fx = 0.0
            else:
                r_fx, _, _ = var_fx(ativo["moeda"], ini, fim_)
                if r_fx is None:
                    avisos.append(f"[bolsas] {ativo['nome']} ({periodo}): sem câmbio {ativo['moeda']} — removido.")
                    continue
            r_usd = (1 + r_local) * (1 + r_fx) - 1
            if abs(r_usd) > (0.60 if periodo == "mes" else 3.0):
                avisos.append(f"[sanidade] {ativo['nome']} ({periodo}): r_usd={r_usd:+.1%} fora do plausível — CONFERIR.")
            resultado[periodo]["bolsas"].append({
                "nome": ativo["nome"], "bandeira": ativo["bandeira"],
                "valor": round(r_usd * 100, 2),
                "destaque": bool(ativo.get("destaque")),
            })
            log.append({"periodo": periodo, "tipo": "bolsa", "nome": ativo["nome"],
                        "ticker": ticker_usado, "data_ini": str(d0), "data_fim": str(d1),
                        "r_local": round(r_local, 6), "r_fx": round(r_fx, 6),
                        "r_usd": round(r_usd, 6)})

    # --- Moedas vs USD ---
    for m in MOEDAS:
        for periodo, (ini, fim_) in janelas.items():
            r_fx, d0, d1 = var_fx(m["codigo"], ini, fim_)
            if r_fx is None:
                avisos.append(f"[moedas] {m['nome']} ({periodo}): sem dados {m['codigo']}=X — removido.")
                continue
            resultado[periodo]["moedas"].append({
                "nome": m["nome"], "bandeira": m["bandeira"],
                "valor": round(r_fx * 100, 2),
                "destaque": bool(m.get("destaque")),
            })
            log.append({"periodo": periodo, "tipo": "moeda", "nome": m["nome"],
                        "ticker": f"{m['codigo']}=X", "data_ini": str(d0),
                        "data_fim": str(d1), "r_local": "", "r_fx": round(r_fx, 6),
                        "r_usd": round(r_fx, 6)})

    for periodo in resultado:
        for grupo in resultado[periodo]:
            resultado[periodo][grupo].sort(key=lambda x: x["valor"], reverse=True)
    return resultado, avisos, log


def main():
    mock = "--mock" in sys.argv
    hoje = date.today()
    ini_12m, ini_mes, fim = limites_periodos(hoje)

    tickers = []
    for a in BOLSAS:
        tickers += a["tickers"]
    tickers += [f"{m['codigo']}=X" for m in MOEDAS]
    tickers = sorted(set(tickers))

    if mock:
        precos = _dados_mock(tickers, ini_12m, fim)
    else:
        precos = baixar_precos(tickers, ini_12m, fim)

    resultado, avisos, log = calcular(precos, ini_12m, ini_mes, fim)

    mes_ref = MESES_PT[fim.month - 1]
    meta = {
        "gerado_em": str(hoje),
        "rotulo_mes": f"{mes_ref.capitalize()} de {fim.year}",
        "rotulo_12m": f"12 meses até {mes_ref[:3]}/{fim.year % 100:02d}",
        "fim_janela": str(fim.date()),
        "inicio_mes": str(ini_mes.date()),
        "inicio_12m": str(ini_12m.date()),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "dados.json").write_text(
        json.dumps({"meta": meta, "dados": resultado}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    pd.DataFrame(log).to_csv(OUTPUT_DIR / "composicao_log.csv", index=False)

    print(f"OK — janelas: mês [{ini_mes.date()} → {fim.date()}], "
          f"12m [{ini_12m.date()} → {fim.date()}]")
    for a in avisos:
        print("AVISO:", a)
    if avisos:
        (OUTPUT_DIR / "avisos.txt").write_text("\n".join(avisos), encoding="utf-8")


def _dados_mock(tickers, ini, fim):
    """Séries sintéticas p/ teste local sem rede."""
    import numpy as np
    rng = np.random.default_rng(42)
    idx = pd.bdate_range(ini - pd.Timedelta(days=20), fim)
    data = {}
    for i, t in enumerate(tickers):
        base = 100 * (1 + i * 0.05)
        ret = rng.normal(0.0003, 0.011, len(idx))
        data[t] = base * pd.Series(1 + ret, index=idx).cumprod()
    return pd.DataFrame(data)


if __name__ == "__main__":
    main()
