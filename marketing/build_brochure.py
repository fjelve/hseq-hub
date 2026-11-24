"""Genera el brochure autocontenido (imágenes incrustadas) y su PDF.

Uso:  python marketing/build_brochure.py
Requiere Playwright con Microsoft Edge o Chromium (solo para el PDF).
Salida: Brochure_HSEQ_Hub.html y Brochure_HSEQ_Hub.pdf en la raíz del repositorio.
"""
import base64
import re
import sys
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parent


def incrustar(html: str) -> str:
    def reemplazo(m):
        datos = base64.b64encode((AQUI / m.group(1)).read_bytes()).decode()
        return f'src="data:image/jpeg;base64,{datos}"'
    return re.sub(r'src="(img/[^"]+\.jpg)"', reemplazo, html)


def main() -> None:
    html = incrustar((AQUI / "brochure.template.html").read_text(encoding="utf-8"))
    salida = RAIZ / "Brochure_HSEQ_Hub.html"
    salida.write_text(html, encoding="utf-8")
    print("HTML:", salida, f"{salida.stat().st_size // 1024} KB")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Sin Playwright: se omite el PDF.")
        return
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="msedge")
        except Exception:
            nav = p.chromium.launch()
        pg = nav.new_page()
        pg.goto(salida.as_uri(), wait_until="networkidle")
        pg.emulate_media(media="print")
        pdf = RAIZ / "Brochure_HSEQ_Hub.pdf"
        pg.pdf(path=str(pdf), format="A4", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        nav.close()
    print("PDF:", pdf, f"{pdf.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
