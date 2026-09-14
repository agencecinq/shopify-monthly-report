"""
Language layer.

Every string that reaches the generated deck lives in `i18n/<lang>.json`, never
in the Python. Number and currency formatting is part of the language, not a
detail: French writes 35 396 € and English writes €35,396, and getting that
wrong makes a report look machine-translated even when every word is right.

    from i18n import Lang
    L = Lang("fr")
    L.t("slides.plan.title")            -> "Le plan des 90 prochains jours"
    L.money(35396.05, "EUR")            -> "35 396 €"
    L.t("priorities.returns.goal", rate=L.pct(0.119))
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
I18N_DIR = os.path.join(os.path.dirname(HERE), "i18n")

NBSP = " "

SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "CHF": "CHF", "CAD": "$",
           "AUD": "$", "JPY": "¥", "SEK": "kr", "DKK": "kr", "NOK": "kr",
           "PLN": "zł", "CZK": "Kč"}

# Symbol placement is a property of the language, not of the currency: English
# writes EUR35,396 and French writes 35 396 EUR. The exception is the handful of
# currencies whose symbol is a word rather than a sign, and which always follow
# the amount in every language.
SUFFIX_CURRENCIES = {"SEK", "DKK", "NOK", "PLN", "CZK", "CHF"}

FALLBACK = "en"


class Lang:
    def __init__(self, code="fr", directory=None):
        self.dir = directory or I18N_DIR
        self.code = code if self._exists(code) else FALLBACK
        self.data = self._load(self.code)
        # The fallback catalogue fills any key a translation has not caught up
        # with, so a partial translation degrades to English instead of
        # printing a raw key into a client deck.
        self.fallback = self._load(FALLBACK) if self.code != FALLBACK else self.data
        f = self.data.get("_format", {})
        self.thousands = f.get("thousands", NBSP)
        self.decimal = f.get("decimal", ",")
        self.currency_position = f.get("currency_position", "after")
        self.currency_space = f.get("currency_space", NBSP)
        self.percent_space = f.get("percent_space", NBSP)

    # -- catalogue ---------------------------------------------------------
    def _path(self, code):
        return os.path.join(self.dir, f"{code}.json")

    def _exists(self, code):
        return bool(code) and os.path.exists(self._path(code))

    def _load(self, code):
        try:
            with open(self._path(code), encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _lookup(self, key, catalogue):
        node = catalogue
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, str) else None

    def t(self, key, **kwargs):
        """Translate a key. Missing keys fall back to English, then to the key."""
        raw = self._lookup(key, self.data) or self._lookup(key, self.fallback)
        if raw is None:
            return key
        try:
            return raw.format(**kwargs) if kwargs else raw
        except (KeyError, IndexError):
            return raw

    def has(self, key):
        return self._lookup(key, self.data) is not None or \
            self._lookup(key, self.fallback) is not None

    def list(self, key):
        """Read a list of strings from the catalogue (used for enumerations)."""
        node = self.data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if not isinstance(node, list):
            node = self.fallback
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return []
                node = node[part]
        return node if isinstance(node, list) else []

    # -- numbers -----------------------------------------------------------
    def num(self, value, dec=0):
        if value is None:
            return self.t("common.na")
        s = f"{abs(value):,.{dec}f}"
        # Swap through placeholders so the two separators cannot collide when
        # one language uses a comma where the other uses a period.
        s = s.replace(",", "\x00").replace(".", "\x01")
        s = s.replace("\x00", self.thousands).replace("\x01", self.decimal)
        return ("-" if value < 0 else "") + s

    def money(self, value, currency="EUR", short=False):
        if value is None:
            return self.t("common.na")
        sym = SYMBOLS.get(currency, currency)
        dec = 0 if (short and abs(value) >= 1000) or abs(value) >= 100 else 2
        body = self.num(value, dec)
        after = self.currency_position == "after" or currency in SUFFIX_CURRENCIES
        if after:
            return f"{body}{self.currency_space}{sym}"
        # Symbol first: the minus sign stays outside, as -$1,200 not $-1,200.
        sign = "-" if body.startswith("-") else ""
        return f"{sign}{sym}{body.lstrip('-')}"

    def pct(self, value, dec=1):
        if value is None:
            return self.t("common.na")
        return f"{self.num(value * 100, dec)}{self.percent_space}%"

    def points(self, value, dec=1):
        """A gap expressed in percentage points, pluralised by the language."""
        n = abs(value) * 100
        word = self.t("common.point_plural" if n >= 2 else "common.point")
        return f"{self.num(n, dec)}{NBSP}{word}"

    def chart_number_format(self, currency=None):
        """Excel number format used by native charts inside the deck."""
        if not currency:
            return "#,##0"
        sym = SYMBOLS.get(currency, currency)
        after = self.currency_position == "after" or currency in SUFFIX_CURRENCIES
        return f'#,##0 "{sym}"' if after else f'"{sym}"#,##0'


def available(directory=None):
    """Language codes shipped with the plugin."""
    d = directory or I18N_DIR
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "fr"
    L = Lang(code)
    print("languages:", available())
    print("code:", L.code)
    for cur in ("EUR", "USD", "GBP"):
        print(f"  {cur}: {L.money(35396.05, cur)} / {L.money(-812.4, cur)} / "
              f"{L.money(42.5, cur)}")
    print("  pct:", L.pct(0.01086, 2), "| points:", L.points(0.029))
    print("  slide:", L.t("slides.plan"), "| milestone:",
          L.t("labels.milestones", values="1,3 % · 1,5 %"))
