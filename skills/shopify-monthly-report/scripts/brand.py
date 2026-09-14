"""
Extraction d'une palette de presentation exploitable a partir du fichier
config/settings_data.json d'un theme Shopify.

Le probleme: chaque theme nomme ses couleurs differemment. Dawn et les themes
OS 2.0 recents utilisent un tableau `color_schemes`. Les themes premium
(Impact, Shrine, Symmetry, Prestige...) utilisent des cles plates. Certains
themes n'exposent presque rien.

La strategie est en trois etages, du plus fiable au plus approximatif, puis
une passe de securite qui garantit que le deck reste lisible meme si le theme
donne une palette impraticable (jaune fluo sur blanc, par exemple).
"""

import json
import re
from collections import Counter

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")

# Cles plates rencontrees dans les themes premium, par role.
FLAT_KEYS = {
    "bg": [
        "background", "body_background", "color_background", "bg_color",
        "colors_background_1", "background_color", "page_background",
    ],
    "ink": [
        "text_color", "body_text_color", "color_text", "colors_text",
        "text", "font_color", "color_body_text",
    ],
    "accent": [
        "primary_button_background", "button_background", "color_button",
        "colors_accent_1", "accent_color", "color_primary", "brand_color",
        "product_primary_badge_background", "checkout_accent_color",
        "colors_solid_button_labels",
    ],
    "accent2": [
        "secondary_button_background", "colors_accent_2", "color_secondary",
        "product_on_sale_accent", "product_rating_color", "accent_color_2",
        "checkout_button_color",
    ],
}

# Familles de polices realistes cote client. Une police Google chargee par le
# thema n'est presque jamais installee sur le poste qui ouvrira le pptx, donc
# on ne l'ecrit dans le fichier que si elle fait partie de cette liste.
SAFE_FONTS = {
    "arial", "helvetica", "calibri", "cambria", "times new roman", "georgia",
    "verdana", "tahoma", "trebuchet ms", "courier new", "garamond",
    "palatino linotype", "century gothic", "futura", "gill sans",
}

FONT_ALIASES = {
    "helvetica": "Arial",
    "helvetica neue": "Arial",
    "arial": "Arial",
    "futura": "Century Gothic",
    "gill sans": "Calibri",
}


# --------------------------------------------------------------------------
# primitives couleur
# --------------------------------------------------------------------------

def norm(h):
    """'#e9ff66' ou 'e9f' -> 'E9FF66'. Retourne None si ce n'est pas une couleur."""
    if not isinstance(h, str):
        return None
    s = h.strip().lstrip("#")
    if len(s) == 3 and all(c in "0123456789abcdefABCDEF" for c in s):
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not all(c in "0123456789abcdefABCDEF" for c in s):
        return None
    return s.upper()


def rgb(h):
    h = norm(h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def hexs(r, g, b):
    clamp = lambda v: max(0, min(255, int(round(v))))
    return "%02X%02X%02X" % (clamp(r), clamp(g), clamp(b))


def luminance(h):
    """Luminance relative WCAG."""
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(a, b):
    """Ratio de contraste WCAG entre deux couleurs, de 1 a 21."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a, b, t):
    """Melange lineaire: t=0 donne a, t=1 donne b."""
    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return hexs(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def saturation(h):
    r, g, b = [v / 255.0 for v in rgb(h)]
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == 0:
        return 0.0
    return (mx - mn) / mx


def is_dark(h):
    return luminance(h) < 0.35


def best_text_on(bg, *candidates):
    """Choisit, parmi les candidats puis noir/blanc, la couleur la plus lisible."""
    pool = [c for c in candidates if norm(c)] + ["111111", "FFFFFF"]
    return max(pool, key=lambda c: contrast(c, bg))


def readable_against(color, bg, minimum=3.0):
    """
    Ramene `color` a un contraste suffisant contre `bg` en l'assombrissant ou
    en l'eclaircissant, sans changer sa teinte. Sert a rendre une couleur de
    marque utilisable pour du texte ou une courbe fine.
    """
    if contrast(color, bg) >= minimum:
        return color
    target = "000000" if not is_dark(bg) else "FFFFFF"
    best, best_ratio = color, contrast(color, bg)
    for i in range(1, 21):
        cand = mix(color, target, i / 20.0)
        ratio = contrast(cand, bg)
        if ratio > best_ratio:
            best, best_ratio = cand, ratio
        if ratio >= minimum:
            return cand
    return best


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def _strip_comments(raw):
    """settings_data.json commence souvent par un bloc /* ... */ non standard."""
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def load_settings(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(_strip_comments(raw))
    except Exception:
        return {}


def _from_color_schemes(current):
    """Etage 1: themes OS 2.0 modernes (Dawn et derives)."""
    schemes = current.get("color_schemes")
    if not isinstance(schemes, dict) or not schemes:
        return None
    # scheme-1 est la palette par defaut du theme dans la quasi-totalite des cas.
    key = next((k for k in ("scheme-1", "scheme_1", "1") if k in schemes), None)
    key = key or sorted(schemes.keys())[0]
    s = schemes.get(key, {})
    s = s.get("settings", s)
    if not isinstance(s, dict):
        return None
    out = {
        "bg": norm(s.get("background")),
        "ink": norm(s.get("text")),
        "accent": norm(s.get("button")) or norm(s.get("secondary_button_background")),
        "accent2": None,
    }
    # Un second scheme porte presque toujours la couleur d'appui de la marque.
    # `shadow` n'en est pas une, on ne s'en sert jamais.
    for k, v in sorted(schemes.items()):
        if k == key:
            continue
        v = v.get("settings", v)
        if not isinstance(v, dict):
            continue
        for cand in (norm(v.get("button")), norm(v.get("background"))):
            if cand and cand not in (out["accent"], out["bg"], out["ink"]):
                out["accent2"] = cand
                break
        if out["accent2"]:
            break
    return out if out["bg"] and out["ink"] else None


def _from_flat_keys(current):
    """Etage 2: themes premium a cles plates."""
    out = {}
    for role, keys in FLAT_KEYS.items():
        for k in keys:
            c = norm(current.get(k))
            if c:
                out[role] = c
                break
    return out if out.get("bg") and out.get("ink") else None


def _from_frequency(raw_text):
    """
    Etage 3: aucune cle reconnue. On ramasse tous les hex du fichier et on
    deduit les roles par luminance et saturation. Grossier mais ca donne
    toujours quelque chose de coherent avec la boutique.
    """
    found = [norm("#" + m.group(1)) for m in HEX_RE.finditer(raw_text)]
    found = [c for c in found if c]
    if not found:
        return None
    counts = Counter(found)
    lights = [c for c in counts if luminance(c) > 0.7]
    darks = [c for c in counts if luminance(c) < 0.2]
    vivid = sorted(
        (c for c in counts if 0.12 < luminance(c) < 0.92 and saturation(c) > 0.35),
        key=lambda c: (-saturation(c), -counts[c]),
    )
    bg = max(lights, key=lambda c: counts[c]) if lights else "FFFFFF"
    ink = max(darks, key=lambda c: counts[c]) if darks else "1A1A1A"
    accent = vivid[0] if vivid else ink
    accent2 = vivid[1] if len(vivid) > 1 else ink
    return {"bg": bg, "ink": ink, "accent": accent, "accent2": accent2}


def _font_family(handle):
    """
    'outfit_n8' -> 'Outfit'. Retourne le nom seulement s'il a une chance
    raisonnable d'etre installe chez le destinataire.
    """
    if not isinstance(handle, str) or not handle:
        return None
    name = re.sub(r"_[in]\d+$", "", handle).replace("_", " ").strip()
    if not name:
        return None
    low = name.lower()
    if low in FONT_ALIASES:
        return FONT_ALIASES[low]
    if low in SAFE_FONTS:
        return " ".join(w.capitalize() if w.islower() else w for w in name.split())
    return None


def build_palette(settings_raw=None, overrides=None):
    """
    Point d'entree. `settings_raw` est le contenu brut de
    config/settings_data.json (texte ou dict). `overrides` permet de forcer
    n'importe quelle cle depuis le fichier de configuration client.
    """
    overrides = overrides or {}
    raw_text = settings_raw if isinstance(settings_raw, str) else json.dumps(settings_raw or {})
    data = load_settings(settings_raw) if settings_raw else {}
    current = data.get("current", data) if isinstance(data, dict) else {}
    if not isinstance(current, dict):
        current = {}

    base = (
        _from_color_schemes(current)
        or _from_flat_keys(current)
        or _from_frequency(raw_text)
        or {}
    )

    source = "theme"
    if not base.get("bg") or not base.get("ink"):
        source = "defaut"
    bg = norm(overrides.get("bg")) or base.get("bg") or "FFFFFF"
    ink = norm(overrides.get("ink")) or base.get("ink") or "1A1A1A"
    accent = norm(overrides.get("accent")) or base.get("accent") or ink
    accent2 = norm(overrides.get("accent2")) or base.get("accent2") or ink

    # --- passe de securite -------------------------------------------------
    # Un fond de slide doit etre franc. Les themes donnent souvent un gris
    # tres clair (#f8f8f8) qui passe bien en web mais grise le deck imprime.
    if not is_dark(bg) and luminance(bg) > 0.86:
        bg = mix(bg, "FFFFFF", 0.65)

    # Le texte doit contraster: certains themes declarent un gris moyen.
    if contrast(ink, bg) < 7.0:
        ink = readable_against(ink, bg, minimum=7.0)

    # L'accent de marque sert surtout de remplissage. On en derive une version
    # lisible pour le texte et les courbes fines, sans perdre la teinte.
    accent_line = readable_against(accent, bg, minimum=3.2)
    accent2_line = readable_against(accent2, bg, minimum=3.2)
    if contrast(accent2_line, accent_line) < 1.6:
        accent2_line = readable_against(mix(accent2_line, ink, 0.55), bg, 3.2)

    surface = mix(bg, ink, 0.05)
    surface_alt = mix(bg, ink, 0.10)
    muted = readable_against(mix(ink, bg, 0.42), bg, minimum=4.0)
    hairline = mix(bg, ink, 0.16)

    # Serie de couleurs pour les graphiques. On part de la marque, puis on
    # decline en luminosite. Une marque monochrome donne une rampe de gris
    # coherente plutot que six fois la meme couleur.
    candidates = [accent_line, ink, accent2_line]
    for base in (accent_line, accent2_line, ink):
        for t in (0.34, 0.58):
            candidates.append(readable_against(mix(base, bg, t), bg, 2.2))
        candidates.append(readable_against(mix(base, ink, 0.5), bg, 2.2))
    deduped = []
    for c in candidates:
        if len(deduped) == 6:
            break
        if all(contrast(c, d) >= 1.35 for d in deduped):
            deduped.append(c)
    step = 0
    while len(deduped) < 6 and step < 12:
        cand = readable_against(mix(ink, bg, 0.2 + 0.12 * step), bg, 2.0)
        if all(contrast(cand, d) >= 1.2 for d in deduped):
            deduped.append(cand)
        step += 1
    while len(deduped) < 6:
        deduped.append(muted_fallback := mix(ink, bg, 0.5))

    # Couleurs de variation. On reste sobre et on garantit la lisibilite.
    up = readable_against("1B7F4B" if not is_dark(bg) else "4ED18A", bg, 4.0)
    down = readable_against("B3261E" if not is_dark(bg) else "FF8A80", bg, 4.0)

    heading = (
        overrides.get("font_heading")
        or _font_family(current.get("heading_font") or current.get("type_header_font"))
        or "Calibri"
    )
    body = (
        overrides.get("font_body")
        or _font_family(current.get("text_font") or current.get("type_body_font"))
        or "Calibri"
    )

    # Slides inversees (couverture, intercalaires). Sur un theme deja sombre on
    # ne peut pas inverser vers le clair sans casser la marque: on assombrit
    # legerement a la place.
    if is_dark(bg):
        invert_bg, invert_ink = mix(bg, ink, 0.10), ink
    else:
        invert_bg, invert_ink = ink, bg
    # Sur fond inverse, l'accent brut de la marque ressort souvent mieux que sa
    # version assombrie pour le texte.
    invert_accent = accent if contrast(accent, invert_bg) >= 4.0 else readable_against(accent, invert_bg, 4.0)

    return {
        "source": source,
        "bg": bg,
        "invert_bg": invert_bg,
        "invert_ink": invert_ink,
        "invert_muted": mix(invert_bg, invert_ink, 0.55),
        "invert_accent": invert_accent,
        "surface": surface,
        "surface_alt": surface_alt,
        "hairline": hairline,
        "ink": ink,
        "muted": muted,
        "accent": accent,
        "accent_line": accent_line,
        "accent_ink": best_text_on(accent, ink, bg),
        "accent2": accent2,
        "accent2_line": accent2_line,
        "series": deduped[:6],
        "up": up,
        "down": down,
        "dark": is_dark(bg),
        "font_heading": heading,
        "font_body": body,
        "theme_fonts": {
            "heading": current.get("heading_font"),
            "body": current.get("text_font"),
        },
    }


if __name__ == "__main__":
    import sys
    raw = open(sys.argv[1], encoding="utf-8").read() if len(sys.argv) > 1 else ""
    print(json.dumps(build_palette(raw), indent=2, ensure_ascii=False))
