"""Générateur d'illustrations 100 % hors ligne (CPU, sans service externe).

Crée une image PNG (rendue avec Pillow, déjà embarqué) et son SVG compagnon
à partir d'une description : graphique en barres, secteurs, organigramme de
processus, mind-map, tableau de comparaison, formule centrée, ou une
illustration générique (titre + texte en page).

Contrat d'honnêteté : on ne FABRIQUE jamais de données. Si le texte ne
contient pas les données demandées ('label=valeur', étapes séparées par
'&' ou ';'), la fonction renvoie une ERREUR qui explique au modèle comment
fournir les données. Il n'y a jamais d'image "de remplissage".
"""

from __future__ import annotations

import os
import re
import time

from PIL import Image, ImageDraw, ImageFont

# --- Dimensions du canevas -------------------------------------------------
W, H = 1024, 768

# --- Palette ----------------------------------------------------------------
HEADER = "#0f172a"       # bandeau sombre
TITLE_TEXT = "#e2e8f0"
ACCENT = "#38bdf8"
TEXT = "#1e293b"
MUTED = "#64748b"
PAPER = "#f8fafc"
GRID = "#cbd5e1"
BARS = ["#38bdf8", "#0ea5e9", "#f59e0b", "#22c55e", "#ef4444",
        "#a855f7", "#14b8a6", "#f43f5e"]

_FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, px)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:                        # très vieille version de Pillow
        return ImageFont.load_default()


def _text_w(d: ImageDraw.ImageDraw, txt: str,
            f) -> int:
    l, _, r, _ = d.textbbox((0, 0), txt, font=f)
    return r - l


def _wrap(d: ImageDraw.ImageDraw, txt: str, f, maxw: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for mot in txt.split():
        test = (cur + " " + mot).strip()
        if _text_w(d, test, f) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = mot
    if cur:
        lines.append(cur)
    return lines


def _truncate(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _first_sentence(prompt: str) -> str:
    text = re.sub(r"(?i)\blabel\s*=\s*valeur\b\s*;?", "", prompt).strip(" ;:,.-")
    first = re.split(r"[.!?;\n]", text)[0].strip()
    if not first:
        return "Données"
    if "=" not in first:
        return first
    # La description mélange un titre et des données : on garde la partie
    # avant les données si elle ressemble à un titre, sinon libellé neutre.
    head = re.split(r"=", first, maxsplit=1)[0].strip(" :,;-")
    head = re.sub(r"\s+[0-9]+(?:\.[0-9]+)?\s*$", "", head).strip(" :,;-")
    head = re.sub(r"(?i)(donnees?|valeurs?|data)\s*$", "", head).strip(" :,;-")
    if not head or re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", head):
        return "Données"
    return head[:60]


# --- Primitives de rendu -----------------------------------------------------
# Chaque primitive est un dict : {"t": ..., "x":..., ...}.
# Deux sérialiseurs : PNG (Pillow) et SVG (texte).


def _render_png(layout: list[dict], title: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    for p in layout:
        t = p["t"]
        if t == "rect":
            d.rounded_rectangle([p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"]],
                                radius=p.get("r", 8), fill=p["fill"])
        elif t == "ellipse":
            d.ellipse([p["x"], p["y"], p["x"] + 2 * p["rx"], p["y"] + 2 * p["ry"]],
                      fill=p["fill"])
        elif t == "line":
            d.line([p["x1"], p["y1"], p["x2"], p["y2"]],
                   fill=p["fill"], width=p.get("width", 3))
        elif t == "arrow":
            d.line([p["x1"], p["y1"], p["x2"], p["y2"]],
                   fill=p["fill"], width=3)
            import math
            ang = math.atan2(p["y2"] - p["y1"], p["x2"] - p["x1"])
            for da in (2.6, -2.6):
                xh = p["x2"] + 14 * math.cos(ang + da)
                yh = p["y2"] + 14 * math.sin(ang + da)
                d.line([p["x2"], p["y2"], xh, yh], fill=p["fill"], width=3)
        elif t == "text":
            f = _font(p["px"])
            d.text((p["x"], p["y"]), p["txt"], font=f, fill=p["fill"],
                   anchor=p.get("anchor", "lm"))
    return img


_SVG_ANCHOR = {"lm": "start", "mm": "middle", "rm": "end", "tm": "start"}


def _svg_text(p: dict) -> str:
    anch = _SVG_ANCHOR.get(p.get("anchor", "lm"), "start")
    base = ('<text x="{x}" y="{y}" font-size="{px}" fill="{fill}" '
            'font-family="Segoe UI, Arial, sans-serif" text-anchor="{anch}">'
            ).format(x=p["x"], y=p["y"], px=p["px"], fill=p["fill"], anch=anch)
    if anch == "start":
        base += ' dominant-baseline="central"'
    elif anch == "middle":
        base += ' dominant-baseline="central"'
    else:
        base += ' dominant-baseline="middle"'
    txt = (p["txt"].replace("&", "&amp;").replace("<", "&lt;")
           .replace(">", "&gt;").replace('"', "&quot;"))
    return base + txt + "</text>"


def _render_svg(layout: list[dict], title: str) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{PAPER}"/>',
    ]
    for p in layout:
        t = p["t"]
        if t == "rect":
            parts.append(
                f'<rect x="{p["x"]}" y="{p["y"]}" width="{p["w"]}" height="{p["h"]}" '
                f'rx="{p.get("r", 8)}" fill="{p["fill"]}"/>')
        elif t == "ellipse":
            parts.append(
                f'<ellipse cx="{p["x"] + p["rx"]}" cy="{p["y"] + p["ry"]}" '
                f'rx="{p["rx"]}" ry="{p["ry"]}" fill="{p["fill"]}"/>')
        elif t == "line":
            parts.append(
                f'<line x1="{p["x1"]}" y1="{p["y1"]}" x2="{p["x2"]}" y2="{p["y2"]}" '
                f'stroke="{p["fill"]}" stroke-width="{p.get("width", 3)}"/>')
        elif t == "arrow":
            import math
            ang = math.atan2(p["y2"] - p["y1"], p["x2"] - p["x1"])
            lx = p["x2"] + 14 * math.cos(ang + 2.6)
            ly = p["y2"] + 14 * math.sin(ang + 2.6)
            rx = p["x2"] + 14 * math.cos(ang - 2.6)
            ry = p["y2"] + 14 * math.sin(ang - 2.6)
            parts.append(
                f'<line x1="{p["x1"]}" y1="{p["y1"]}" x2="{p["x2"]}" y2="{p["y2"]}" '
                f'stroke="{p["fill"]}" stroke-width="3"/>')
            parts.append(
                f'<polygon points="{p["x2"]},{p["y2"]} {lx},{ly} {rx},{ry}" '
                f'fill="{p["fill"]}"/>')
        elif t == "text":
            parts.append(_svg_text(p))
    parts.append("</svg>")
    return "\n".join(parts)


def _header(title: str) -> list[dict]:
    return [
        {"t": "rect", "x": 0, "y": 0, "w": W, "h": 96, "fill": HEADER, "r": 0},
        {"t": "text", "x": 40, "y": 52, "txt": _truncate(title, 70),
         "px": 30, "fill": TITLE_TEXT, "anchor": "lm"},
    ]


def _save(sortie: str, layout: list[dict], title: str) -> str:
    dossier = os.path.dirname(sortie)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    img = _render_png(layout, title)
    img.save(sortie, "PNG")
    svg_path = os.path.splitext(sortie)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as fh:
        fh.write(_render_svg(layout, title))
    return (f"OK: illustration générée dans {os.path.basename(sortie)} "
            f"({W}x{H}, PNG + SVG compagnon).")


# --- Extraction des données (honnête : jamais de fabrication) ---------------


def _pairs(prompt: str) -> list[tuple[str, float]]:
    """Extrait des paires 'label=valeur' (ex: 2020=80 ; 2021=90)."""
    out = []
    for m in re.finditer(r"([^,;=\n:]{1,40}?)\s*=\s*(\d+(?:[.,]\d+)?)", prompt):
        label = re.sub(r"^\s*(?:-\s*|\*\s*|•\s*|\d+[.)]\s*)", "", m.group(1)).strip()
        if not label:
            continue
        val = float(m.group(2).replace(",", "."))
        if not out or out[-1][0] != label:
            out.append((label, val))
    return out


def _items(prompt: str, maxn: int = 8) -> list[str]:
    """Étapes/items séparés par ';', '->' ou retours à la ligne."""
    parts = re.split(r"[;\n]|(?:->|→)", prompt)
    out = []
    for p_ in parts:
        p_ = re.sub(r"^\s*(?:[\d()\-*•·]+\.?)\s*", "", p_).strip()
        if p_:
            out.append(p_)
    return out[:maxn]


# --- Genres d'illustrations ---------------------------------------------------


def _bar_chart(prompt: str, title: str) -> str | list[dict]:
    pairs = _pairs(prompt)
    if len(pairs) < 2:
        return ("ERREUR: pour un graphique, donnez au moins 2 valeurs "
                "'label=valeur', ex: 'graphique en barres : 2020=80 ; 2021=90 ; 2022=95'.")
    labels = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    vmax = max(vals) or 1.0
    layout = _header(title)
    plot = {"x": 150, "y": 160, "w": W - 300, "h": H - 160 - 150}
    # grille horizontale + étiquettes
    for i in range(5):
        gy = plot["y"] + plot["h"] * i / 4
        layout.append({"t": "line", "x1": plot["x"], "y1": gy,
                       "x2": plot["x"] + plot["w"], "y2": gy, "fill": GRID, "width": 1})
        val = vmax * (4 - i) / 4
        layout.append({"t": "text", "x": plot["x"] - 12, "y": gy,
                       "txt": f"{val:.0f}", "px": 16, "fill": MUTED, "anchor": "rm"})
    n = len(labels)
    slot = plot["w"] / n
    bw = min(64, slot * 0.55)
    for i, (lab, v) in enumerate(zip(labels, vals)):
        bh = plot["h"] * v / vmax
        bx = plot["x"] + slot * i + (slot - bw) / 2
        by = plot["y"] + plot["h"] - bh
        layout.append({"t": "rect", "x": bx, "y": by, "w": bw, "h": bh,
                       "fill": BARS[i % len(BARS)], "r": 6})
        layout.append({"t": "text", "x": bx + bw / 2, "y": by - 10,
                       "txt": f"{v:g}", "px": 18, "fill": TEXT, "anchor": "mm"})
        layout.append({"t": "text", "x": bx + bw / 2, "y": plot["y"] + plot["h"] + 26,
                       "txt": _truncate(lab, 16), "px": 16, "fill": TEXT, "anchor": "mm"})
    layout.append({"t": "text", "x": plot["x"], "y": plot["y"] + plot["h"] + 70,
                   "txt": _truncate(title, 90), "px": 20, "fill": MUTED, "anchor": "lm"})
    return layout


def _pie_chart(prompt: str, title: str) -> str | list[dict]:
    pairs = _pairs(prompt)
    if len(pairs) < 2:
        return ("ERREUR: pour un diagramme en secteurs, donnez au moins 2 valeurs "
                "'label=valeur', ex: 'répartition : Maths=40 ; Français=30 ; Physique=30'.")
    total = sum(v for _, v in pairs)
    if total <= 0:
        return "ERREUR: somme des valeurs nulle, impossible à représenter."
    layout = _header(title)
    cx, cy, R = W // 2 - 150, H // 2 + 40, 220
    layout.append({"t": "ellipse", "x": cx - R, "y": cy - R, "rx": R, "ry": R,
                   "fill": "#e2e8f0"})
    start = -90.0
    import math
    for i, (lab, v) in enumerate(pairs):
        sweep = 360.0 * v / total
        mid = start + sweep / 2
        for step in range(1, int(sweep) + 1):
            a1 = math.radians(start + step - 1)
            a2 = math.radians(start + step)
            layout.append({"t": "line",
                           "x1": cx + R * math.cos(a1), "y1": cy + R * math.sin(a1),
                           "x2": cx + R * math.cos(a2), "y2": cy + R * math.sin(a2),
                           "fill": BARS[i % len(BARS)], "width": 6})
        start += sweep
        ang = math.radians(mid)
        lx = cx + (R + 60) * math.cos(ang)
        ly = cy + (R + 60) * math.sin(ang)
        layout.append({"t": "text", "x": lx, "y": ly, "px": 20, "fill": TEXT,
                       "txt": f"{lab} ({v / total * 100:.0f}%)", "anchor": "mm"})
    layout.append({"t": "text", "x": cx, "y": cy, "px": 22, "fill": MUTED,
                   "txt": _truncate(title, 40), "anchor": "mm"})
    return layout


def _flow(prompt: str, title: str) -> str | list[dict]:
    items = [it for it in _items(prompt) if it.lower() != title.lower()]
    if len(items) < 2:
        return ("ERREUR: pour un organigramme, donnez les étapes séparées par ';', "
                "ex: 'processus : collecte ; traitement ; analyse ; présentation'.")
    layout = _header(title)
    cols = 4 if len(items) <= 4 else 3
    rows = (len(items) + cols - 1) // cols
    bw, bh = 200, 96
    x0 = (W - (cols * bw + (cols - 1) * 60)) / 2
    y0 = 180
    for i, item in enumerate(items):
        r, c = divmod(i, cols)
        x = x0 + c * (bw + 60)
        y = y0 + r * (bh + 90)
        layout.append({"t": "rect", "x": x, "y": y, "w": bw, "h": bh,
                       "fill": ACCENT, "r": 12})
        layout.append({"t": "text", "x": x + bw / 2, "y": y + bh / 2,
                       "txt": _truncate(item, 40), "px": 20, "fill": "#082f49",
                       "anchor": "mm"})
        if c < cols - 1:
            layout.append({"t": "arrow", "x1": x + bw + 4, "y1": y + bh / 2,
                           "x2": x + bw + 56, "y2": y + bh / 2, "fill": TEXT})
        elif r < rows - 1:
            layout.append({"t": "arrow", "x1": x + bw / 2, "y1": y + bh + 4,
                           "x2": x + bw / 2, "y2": y + bh + 86, "fill": TEXT})
    return layout


def _mindmap(prompt: str, title: str) -> str | list[dict]:
    items = [it for it in _items(prompt) if it.lower() != title.lower()]
    if not items:
        return ("ERREUR: pour une carte mentale, donnez le sujet puis les branches "
                "séparées par ';', ex: 'carte mentale : le système solaire ; "
                "Mercure ; Vénus ; Terre ; Mars'.")
    layout = _header(title)
    cx, cy = W // 2, H // 2
    layout.append({"t": "ellipse", "x": cx - 120, "y": cy - 55, "rx": 120, "ry": 55,
                   "fill": HEADER})
    layout.append({"t": "text", "x": cx, "y": cy, "px": 24, "fill": TITLE_TEXT,
                   "txt": _truncate(title, 26), "anchor": "mm"})
    n = len(items)
    import math
    r1, r2 = 210, 330
    for i, item in enumerate(items):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        bx = cx + r2 * math.cos(ang)
        by = cy + r2 * math.sin(ang) * 0.8
        layout.append({"t": "line", "x1": cx + 150 * math.cos(ang),
                       "y1": cy + 60 * math.sin(ang) * 0.8,
                       "x2": cx + (r2 - 95) * math.cos(ang),
                       "y2": cy + (r2 - 95) * math.sin(ang) * 0.8,
                       "fill": MUTED, "width": 2})
        layout.append({"t": "rect", "x": bx - 85, "y": by - 26, "w": 170, "h": 52,
                       "fill": BARS[i % len(BARS)], "r": 10})
        layout.append({"t": "text", "x": bx, "y": by, "px": 17, "fill": "#082f49",
                       "txt": _truncate(item, 26), "anchor": "mm"})
    return layout


def _compare(prompt: str, title: str) -> str | list[dict]:
    p = prompt
    m = re.search(r"(?:pour|avantages)\s*[:\-]\s*(.*?)\s*(?:contre|inconvenients|"
                  r"inconvénients)\s*[:\-]\s*(.*)$", p, re.I | re.S)
    if m:
        left = _items(m.group(1))
        right = _items(m.group(2))
        ltitle, rtitle = "POUR", "CONTRE"
        if not left and not right:
            return ("ERREUR: donnez des éléments 'pour: ...' et 'contre: ...', "
                    "ex: 'avantages et inconvénients : pour: rapide ; précis ; "
                    "contre: lent ; lourd'.")
    else:
        items = _items(prompt)
        if len(items) < 4:
            return ("ERREUR: pour un tableau de comparaison, donnez les éléments "
                    "séparés par ';' (au moins 4), ou précisez 'pour: ... contre: ...'.")
        half = (len(items) + 1) // 2
        left, right = items[:half], items[half:]
        ltitle, rtitle = "COLONNE A", "COLONNE B"
    layout = _header(title)
    cols_w = 360
    x0 = (W - 2 * cols_w - 60) / 2
    y0 = 170
    for x, titre, data, color in ((x0, ltitle, left, BARS[0]),
                                  (x0 + cols_w + 60, rtitle, right, BARS[4])):
        layout.append({"t": "rect", "x": x, "y": y0, "w": cols_w, "h": 56,
                       "fill": color, "r": 10})
        layout.append({"t": "text", "x": x + cols_w / 2, "y": y0 + 28, "px": 22,
                       "fill": "#fff", "txt": titre, "anchor": "mm"})
        by = y0 + 70
        for item in data:
            layout.append({"t": "rect", "x": x, "y": by, "w": cols_w, "h": 54,
                           "fill": "#e2e8f0", "r": 8})
            layout.append({"t": "text", "x": x + 16, "y": by + 27, "px": 17,
                           "fill": TEXT, "txt": _truncate(item, 42), "anchor": "lm"})
            by += 68
    return layout


def _equation(prompt: str, title: str) -> list[dict]:
    expr = re.sub(r"(?i)^.*?\b(équation|equation|formule)\b\s*:?\s*", "",
                  prompt).strip() or title
    layout = _header(title)
    layout.append({"t": "rect", "x": 130, "y": 250, "w": W - 260, "h": 240,
                   "fill": "#e2e8f0", "r": 16})
    layout.append({"t": "text", "x": W / 2, "y": H / 2, "px": 46, "fill": HEADER,
                   "txt": _truncate(expr, 42), "anchor": "mm"})
    layout.append({"t": "text", "x": W / 2, "y": H / 2 + 150, "px": 18,
                   "fill": MUTED, "txt": "Équation du cours", "anchor": "mm"})
    return layout


def _generic(prompt: str, title: str) -> list[dict]:
    layout = _header(title)
    body = _truncate(prompt, 300)
    layout.append({"t": "rect", "x": 120, "y": 160, "w": W - 240, "h": 380,
                   "fill": "#e2e8f0", "r": 18})
    # décoration : trois pastilles
    for i, col in enumerate(BARS[:3]):
        layout.append({"t": "ellipse", "x": 180 + i * 220, "y": 210,
                       "rx": 46, "ry": 46, "fill": col})
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = _font(24)
    lines = _wrap(d, body, f, W - 400)
    y = 360
    for line in lines[:8]:
        layout.append({"t": "text", "x": W / 2, "y": y, "px": 24, "fill": TEXT,
                       "txt": line, "anchor": "mm"})
        y += 40
    layout.append({"t": "text", "x": W / 2, "y": 580, "px": 18, "fill": MUTED,
                   "txt": "Illustration générée hors ligne (PNG + SVG)",
                   "anchor": "mm"})
    return layout


def _looks_like_formula(prompt: str) -> bool:
    """Vrai si le texte '...=...' ressemble à une formule mathématique
    (opérateurs ou une inconnue), pas à une donnée label=valeur."""
    m = re.search(r"([^=;]+?)\s*=\s*([^=;]+)", prompt)
    if not m:
        return False
    lhs, rhs = m.group(1), m.group(2)
    if any(c in (lhs + rhs) for c in "+-*/^"):
        return True
    if re.search(r"(?i)\b(sqrt|sin|cos|tan|log|ln|exp|pi)\b", lhs + rhs):
        return True
    return re.match(r"(?i)^[a-z]\s*$", lhs.strip()) is not None


def _detect(prompt: str) -> str:
    p = prompt.lower()
    # Des mots-clés de genre explicites ont priorité.
    if any(k in p for k in ("graphique", "barre", "histogramme", "statistique",
                            "evolution", "évolution")):
        return "bar"
    if any(k in p for k in ("secteur", "repartition", "répartition", "camembert",
                            "pourcentage")):
        return "pie"
    if any(k in p for k in ("processus", "etape", "étape", "workflow",
                            "chronologie", "deroulement", "déroulement",
                            "organigramme", "process")):
        return "flow"
    if any(k in p for k in ("mind", "carte mentale", "idee", "idée",
                            "brainstorming")):
        return "mindmap"
    if any(k in p for k in ("compar", "diff", "pour et contre", "pour/contre",
                            "avantages", "inconvenient", "inconvénient")):
        return "compare"
    # Un jeu de données 'label=valeur' sans genre explicite -> graphique en
    # barres (le plus demandé) : évite le faux positif 'equation'.
    if len(_pairs(prompt)) >= 2:
        return "bar"
    if ("équation" in p or "equation" in p or "formule" in p
            or _looks_like_formula(prompt)):
        return "equation"
    return "generic"


def generer(prompt: str, sortie: str) -> str:
    """Crée l'illustration à partir de la description. Renvoie le message au modèle."""
    prompt = (prompt or "").strip()
    if not prompt:
        return "ERREUR: description de l'image vide."
    title = _first_sentence(prompt)
    kind = _detect(prompt)
    builders = {"bar": _bar_chart, "pie": _pie_chart, "flow": _flow,
                "mindmap": _mindmap, "compare": _compare,
                "equation": _equation, "generic": _generic}
    result = builders[kind](prompt, title)
    if isinstance(result, str):                    # message d'ERREUR honnête
        return result
    message = _save(sortie, result, title)
    return message + (f"\nGenre: {kind}.")
