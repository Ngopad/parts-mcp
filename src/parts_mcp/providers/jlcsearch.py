"""Klient til jlcsearch (tscircuit): JLCPCB/LCSC-lagerkatalog. Gratis, ingen nøgle."""

import re

import httpx

from .common import TTLCache, summary


class JlcSearchClient:
    name = "jlcsearch"

    @classmethod
    def from_env(cls) -> "JlcSearchClient":
        return cls()  # kræver ingen nøgle

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(base_url="https://jlcsearch.tscircuit.com", timeout=30)
        self._cache = TTLCache()

    async def _components(self, search: str) -> list[dict]:
        if (hit := self._cache.get(search)) is not None:
            return hit
        r = await self._http.get("/components/list.json", params={"search": search})
        r.raise_for_status()
        components = r.json().get("components") or []
        self._cache.set(search, components)
        return components

    def _summary(self, c: dict) -> dict:
        lcsc = f"C{c['lcsc']}"
        # Pris kommer som "1-499:0.0202,500-2999:0.0159,..."
        breaks = []
        for part in str(c.get("price") or "").split(","):
            qty, _, price = part.partition(":")
            if price:
                breaks.append({"qty": int(qty.split("-")[0]), "price": float(price)})
        return {
            **summary(
                supplier=self.name,
                mpn=c.get("mfr"),
                manufacturer=None,  # jlcsearch oplyser ikke producent
                description=c.get("description"),
                supplier_pn=lcsc,
                in_stock=c.get("stock"),
                price_breaks=breaks,
                currency="USD",
                url=f"https://www.lcsc.com/product-detail/{lcsc}.html",
                datasheet=None,
            ),
            "package": c.get("package"),
            # Basic-dele har ingen opsætningsgebyr ved JLCPCB-montage
            "jlc_basic": c.get("is_basic"),
        }

    async def search(self, keywords: str, limit: int = 10) -> list[dict]:
        # jlcsearch' fuldtekstindeks returnerer pt. urelaterede dele (tscircuit/jlcsearch#611),
        # så behold kun resultater der faktisk indeholder alle søgeordene
        words = keywords.casefold().split()
        hits = []
        for c in await self._components(keywords):
            text = f"C{c['lcsc']} {c.get('mfr')} {c.get('package')} {c.get('description')}".casefold()
            if all(w in text for w in words):
                hits.append(self._summary(c))
        return hits[:limit]

    async def part(self, lcsc_number: str) -> dict:
        if not re.fullmatch(r"[Cc]?\d+", lcsc_number.strip()):
            raise LookupError("jlcsearch slår kun op på LCSC-nummer, f.eks. 'C7950'")
        number = int(lcsc_number.strip().lstrip("Cc"))
        c = next((x for x in await self._components(f"C{number}") if x["lcsc"] == number), None)
        if c is None:
            raise LookupError(f"jlcsearch kender ikke 'C{number}'")
        return self._summary(c)
