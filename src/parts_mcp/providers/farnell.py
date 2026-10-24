"""Lille klient til element14/Farnell Product Search API (API-nøgle, kun read)."""

import os

import httpx

from .common import TTLCache, summary


class FarnellClient:
    name = "farnell"

    @classmethod
    def from_env(cls) -> "FarnellClient | None":
        return cls() if os.getenv("FARNELL_API_KEY") else None

    def __init__(self) -> None:
        self.api_key = os.environ["FARNELL_API_KEY"]
        self.store = os.getenv("FARNELL_STORE", "dk.farnell.com")
        # API'et oplyser ikke valuta; priserne er i butikkens valuta
        self.currency = os.getenv("FARNELL_CURRENCY", "DKK")
        self._http = httpx.AsyncClient(base_url="https://api.element14.com/catalog", timeout=30)
        self._cache = TTLCache()

    async def _products(self, term: str, limit: int) -> list[dict]:
        cache_key = f"{term} {limit}"
        if (hit := self._cache.get(cache_key)) is not None:
            return hit
        r = await self._http.get(
            "/products",
            params={
                "term": term,
                "storeInfo.id": self.store,
                "resultsSettings.offset": 0,
                "resultsSettings.numberOfResults": limit,
                "resultsSettings.responseGroup": "large",
                "callInfo.responseDataFormat": "JSON",
                "callInfo.apiKey": self.api_key,
            },
        )
        r.raise_for_status()
        # Svaret ligger under en nøgle der afhænger af søgetypen, f.eks. keywordSearchReturn
        ret = next(iter(r.json().values()), {}) or {}
        products = ret.get("products") or []
        self._cache.set(cache_key, products)
        return products

    def _summary(self, p: dict) -> dict:
        # displayName er "PRODUCENT - MPN - beskrivelse"
        description = (p.get("displayName") or "").split(" - ", 2)[-1]
        return summary(
            supplier=self.name,
            mpn=p.get("translatedManufacturerPartNumber"),
            manufacturer=p.get("brandName") or p.get("vendorName"),
            description=description,
            supplier_pn=p.get("sku"),
            in_stock=(p.get("stock") or {}).get("level", p.get("inv")),
            price_breaks=[{"qty": x["from"], "price": x["cost"]} for x in p.get("prices") or []],
            currency=self.currency,
            url=f"https://{self.store}/search?st={p.get('sku')}",
            datasheet=next((d.get("url") for d in p.get("datasheets") or []), None),
        )

    async def search(self, keywords: str, limit: int = 10) -> list[dict]:
        return [self._summary(p) for p in await self._products(f"any:{keywords}", limit)]

    async def part(self, part_number: str) -> dict:
        # Farnell-varenumre er rene tal, ellers søges der på producentens nummer
        term = f"id:{part_number}" if part_number.isdigit() else f"manuPartNum:{part_number}"
        products = await self._products(term, 1)
        if not products:
            raise LookupError(f"Farnell kender ikke '{part_number}'")
        p = products[0]
        return {
            **self._summary(p),
            "parameters": {a["attributeLabel"]: a["attributeValue"] for a in p.get("attributes") or []},
        }
