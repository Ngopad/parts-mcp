"""Fælles hjælpere for leverandør-klienterne: cache, prisparsing og fælles resultatformat."""

import os
import re
import time

CACHE_SECONDS = int(os.getenv("CACHE_SECONDS", "3600"))


class TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        hit = self._data.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
        self._data.pop(key, None)  # fjern udløbne, så cachen ikke vokser for evigt
        return None

    def set(self, key: str, value) -> None:
        self._data[key] = (time.time(), value)


def parse_price(text: str | float | None) -> float | None:
    """'1.234,56 kr.' / '$1,234.56' / 1.38 -> float."""
    if text is None or isinstance(text, (int, float)):
        return text
    # strip() fjerner f.eks. punktummet fra "kr."
    s = re.sub(r"[^\d,.]", "", text).strip(".,")
    if "," in s and "." in s:
        # Det sidste skilletegn er decimaltegnet
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def summary(
    *,
    supplier: str,
    mpn: str | None,
    manufacturer: str | None,
    description: str | None,
    supplier_pn: str | None,
    in_stock: int | None,
    price_breaks: list[dict],
    currency: str | None,
    url: str | None,
    datasheet: str | None,
) -> dict:
    """Samme felter for alle leverandører, så resultaterne kan sammenlignes."""
    return {
        "supplier": supplier,
        "mpn": mpn,
        "manufacturer": manufacturer,
        "description": description,
        "supplier_pn": supplier_pn,
        "in_stock": in_stock,
        "unit_price": price_breaks[0]["price"] if price_breaks else None,
        "currency": currency,
        "price_breaks": price_breaks,
        "url": url,
        "datasheet": datasheet or None,
    }
