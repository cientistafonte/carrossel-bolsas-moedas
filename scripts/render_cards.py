#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Renderiza os 4 cards (bolsas/moedas × mês/12m) a partir de output/dados.json.

Saída: JPEGs 1080×1350 em alta resolução (scale 2x, reamostrado p/ 1080)
em output/cards/. JPEG é obrigatório: a Instagram Content Publishing API
só aceita image_url em formato JPEG.
"""

import json
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TEMPLATE = (BASE / "templates" / "card_template.html").read_text(encoding="utf-8")
OUT = BASE / "output"
CARDS = OUT / "cards"


def fmt_pct(v: float) -> str:
    s = f"{v:+.2f}".replace(".", ",").replace("+", "")
    return f"-{s.lstrip('-')}%" if v < 0 else f"{s}%"


def gerar_candles(seed: int) -> str:
    """Candles decorativos determinísticos p/ marca d'água."""
    rnd = random.Random(seed)
    partes, x, y = [], 640, 900
    for _ in range(26):
        h = rnd.randint(30, 110)
        y += rnd.randint(-40, 34)
        y = max(700, min(1250, y))
        cor = "#1c2b5a" if rnd.random() > .45 else "#c0392b"
        partes.append(
            f'<line x1="{x+7}" y1="{y-18}" x2="{x+7}" y2="{y+h+18}" stroke="{cor}" stroke-width="3"/>'
            f'<rect x="{x}" y="{y}" width="14" height="{h}" rx="2" fill="{cor}"/>')
        x += 17
    return "".join(partes)


def montar_linhas(itens: list) -> str:
    html = []
    divisor_inserido = False
    for i, item in enumerate(itens):
        if not divisor_inserido and item["valor"] < 0:
            html.append(
                '<div class="divisor">'
                '<div class="setas"><span class="up">▲</span><span class="down">▼</span></div>'
                '<div class="traco"></div></div>')
            divisor_inserido = True
        classe = "linha destaque" if item["destaque"] else "linha"
        html.append(
            f'<div class="{classe}">'
            f'<span class="bandeira">{item["bandeira"]}</span>'
            f'<span class="nome">{item["nome"]}</span>'
            f'<span class="valor">{fmt_pct(item["valor"])}</span></div>')
    return "\n".join(html)


def render_html(titulo, subtitulo, itens, seed):
    return (TEMPLATE
            .replace("{{TITULO}}", titulo)
            .replace("{{SUBTITULO}}", subtitulo)
            .replace("{{LINHAS}}", montar_linhas(itens))
            .replace("{{CANDLES}}", gerar_candles(seed)))


def main():
    dados = json.loads((OUT / "dados.json").read_text(encoding="utf-8"))
    meta, d = dados["meta"], dados["dados"]

    cards = [
        # (arquivo, título, subtítulo, itens)
        ("bolsas_mes",  "Bolsas Mundiais em Dólar", meta["rotulo_mes"],  d["mes"]["bolsas"]),
        ("moedas_mes",  "Moedas frente ao Dólar",   meta["rotulo_mes"],  d["mes"]["moedas"]),
        ("bolsas_12m",  "Bolsas Mundiais em Dólar", meta["rotulo_12m"],  d["12m"]["bolsas"]),
        ("moedas_12m",  "Moedas frente ao Dólar",   meta["rotulo_12m"],  d["12m"]["moedas"]),
    ]

    CARDS.mkdir(parents=True, exist_ok=True)
    htmls = []
    for i, (nome, titulo, sub, itens) in enumerate(cards):
        html = render_html(titulo, sub, itens, seed=i + 7)
        caminho = CARDS / f"{nome}.html"
        caminho.write_text(html, encoding="utf-8")
        htmls.append((nome, caminho))

    from playwright.sync_api import sync_playwright
    from PIL import Image

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350},
                                device_scale_factor=2)
        for nome, caminho in htmls:
            page.goto(caminho.as_uri())
            page.wait_for_timeout(400)
            png = CARDS / f"{nome}.png"
            page.screenshot(path=str(png))
            # Instagram Graph API exige JPEG
            img = Image.open(png).convert("RGB")
            img = img.resize((1080, 1350), Image.LANCZOS)
            img.save(CARDS / f"{nome}.jpg", "JPEG", quality=92)
            png.unlink()
            print(f"gerado: cards/{nome}.jpg")
        browser.close()


if __name__ == "__main__":
    main()
