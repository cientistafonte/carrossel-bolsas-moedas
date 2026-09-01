#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Publica DOIS carrosséis no Instagram via Content Publishing API (Graph API):
  1) Mês encerrado  → [bolsas_mes.jpg, moedas_mes.jpg]
  2) Últimos 12 meses → [bolsas_12m.jpg, moedas_12m.jpg]

Pré-requisitos (ver SETUP_META.md):
  - Conta Instagram Profissional (Creator/Business) vinculada a uma Página FB
  - App Meta com permissões instagram_basic + instagram_content_publish
  - As imagens precisam estar em URL PÚBLICA e em JPEG. O workflow commita
    os JPEGs no repositório (público) e usa raw.githubusercontent.com.

Env vars (GitHub Secrets):
  IG_USER_ID       — ID da conta Instagram Business/Creator
  IG_ACCESS_TOKEN  — token de longa duração (~60 dias; renovar!)
  IMAGE_BASE_URL   — ex.: https://raw.githubusercontent.com/usuario/repo/main/output/cards
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

GRAPH = "https://graph.facebook.com/v21.0"
IG_USER = os.environ["IG_USER_ID"]
TOKEN = os.environ["IG_ACCESS_TOKEN"]
BASE_URL = os.environ["IMAGE_BASE_URL"].rstrip("/")

OUT = Path(__file__).resolve().parent.parent / "output"


def _post(endpoint: str, **params):
    params["access_token"] = TOKEN
    r = requests.post(f"{GRAPH}/{endpoint}", data=params, timeout=60)
    dados = r.json()
    if "error" in dados:
        raise RuntimeError(f"Graph API erro em {endpoint}: {json.dumps(dados['error'], ensure_ascii=False)}")
    return dados


def _esperar_container(container_id: str, timeout_s: int = 120):
    """Containers de imagem costumam ficar prontos em segundos, mas o status
    deve ser verificado antes do publish (evita erro 'Media not ready')."""
    fim = time.time() + timeout_s
    while time.time() < fim:
        r = requests.get(f"{GRAPH}/{container_id}",
                         params={"fields": "status_code", "access_token": TOKEN},
                         timeout=30).json()
        status = r.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} com ERROR: {r}")
        time.sleep(3)
    raise TimeoutError(f"Container {container_id} não ficou pronto em {timeout_s}s")


def publicar_carrossel(imagens: list, legenda: str) -> str:
    filhos = []
    for img in imagens:
        c = _post(f"{IG_USER}/media",
                  image_url=f"{BASE_URL}/{img}",
                  is_carousel_item="true")
        _esperar_container(c["id"])
        filhos.append(c["id"])
        print(f"  container ok: {img} → {c['id']}")

    carrossel = _post(f"{IG_USER}/media",
                      media_type="CAROUSEL",
                      children=",".join(filhos),
                      caption=legenda)
    _esperar_container(carrossel["id"])
    pub = _post(f"{IG_USER}/media_publish", creation_id=carrossel["id"])
    print(f"  publicado: media_id={pub['id']}")
    return pub["id"]


def montar_legenda(meta: dict, dados: dict, periodo: str) -> str:
    rotulo = meta["rotulo_mes"] if periodo == "mes" else meta["rotulo_12m"]
    bolsas = dados[periodo]["bolsas"]
    moedas = dados[periodo]["moedas"]
    ibov = next((x for x in bolsas if x["destaque"]), None)
    real = next((x for x in moedas if x["destaque"]), None)

    def pct(v):
        return f"{v:+.2f}".replace(".", ",") + "%"

    linhas = [f"📊 {rotulo} — bolsas mundiais em dólar e moedas frente ao dólar."]
    if ibov:
        pos = bolsas.index(ibov) + 1
        linhas.append(f"🇧🇷 Ibovespa em dólar: {pct(ibov['valor'])} "
                      f"({pos}º de {len(bolsas)}).")
    if real:
        pos = moedas.index(real) + 1
        linhas.append(f"💵 Real frente ao dólar: {pct(real['valor'])} "
                      f"({pos}º de {len(moedas)}).")
    linhas.append("")
    linhas.append("Fonte: Yahoo Finance. Índices em moeda local compostos com a "
                  "variação cambial de cada país frente ao dólar.")
    linhas.append("Conteúdo informativo e educacional. Não constitui recomendação "
                  "de investimento.")
    linhas.append("")
    linhas.append("#investimentos #mercadofinanceiro #bolsadevalores #dolar "
                  "#ibovespa #economia")
    return "\n".join(linhas)


def main():
    payload = json.loads((OUT / "dados.json").read_text(encoding="utf-8"))
    meta, dados = payload["meta"], payload["dados"]

    apenas = sys.argv[1] if len(sys.argv) > 1 else "ambos"  # mes | 12m | ambos

    if apenas in ("mes", "ambos"):
        print("Publicando carrossel do mês encerrado…")
        publicar_carrossel(["bolsas_mes.jpg", "moedas_mes.jpg"],
                           montar_legenda(meta, dados, "mes"))
    if apenas in ("12m", "ambos"):
        # pequena pausa entre publicações
        time.sleep(10)
        print("Publicando carrossel de 12 meses…")
        publicar_carrossel(["bolsas_12m.jpg", "moedas_12m.jpg"],
                           montar_legenda(meta, dados, "12m"))
    print("Concluído.")


if __name__ == "__main__":
    main()
