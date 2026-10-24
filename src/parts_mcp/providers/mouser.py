"""Lille klient til Mouser Search API v1 (API-nøgle, kun read)."""

import os

import httpx

from .common import TTLCache, parse_price, summary


class MouserClient:
    name = "mouser"

    @classmethod
    def from_env(cls) -> "MouserClient | None":
        return cls() if os.getenv("MOUSER_API_KEY") else None

    def __init__(self) -> None:
        self.api_key = os.environ["MOUSER_API_KEY"]
        self._http = httpx.AsyncClient(base_url="https://api.mouser.com/api/v1", timeout=30)
        self._cache = TTLCache()

    async def _post(self, path: str, body: dict) -> list[dict]:
        cache_key = f"{path} {body}"
        if (hit := self._cache.get(cache_key)) is not None:
            return hit
        r = await self._http.post(path, params={"apiKey": self.api_key}, json=body)
        r.raise_for_status()
        data = r.json()
        # Mouser svarer 200 med fejl i "Errors"
        if errors := data.get("Errors"):
            raise RuntimeError(f"Mouser: {errors[0].get('Message')}")
        # "N/A" = Mouser sælger ikke varen i vores region
        parts = [p for p in (data.get("SearchResults") or {}).get("Parts") or [] if p.get("MouserPartNumber") != "N/A"]
        self._cache.set(cache_key, parts)
        return parts

    def _summary(self, p: dict) -> dict:
        breaks = p.get("PriceBreaks") or []
        stock = p.get("AvailabilityInStock")
        return summary(
            supplier=self.name,
            mpn=p.get("ManufacturerPartNumber"),
            manufacturer=p.get("Manufacturer"),
            description=(p.get("Description") or "").strip(),
            supplier_pn=p.get("MouserPartNumber"),
            in_stock=int(stock) if stock else 0,
            price_breaks=[{"qty": b["Quantity"], "price": parse_price(b["Price"])} for b in breaks],
            currency=breaks[0].get("Currency") if breaks else None,
            url=p.get("ProductDetailUrl"),
            datasheet=p.get("DataSheetUrl"),
        )

    async def search(self, keywords: str, limit: int = 10) -> list[dict]:
        parts = await self._post(
            "/search/keyword",
            {"SearchByKeywordRequest": {"keyword": keywords, "records": limit, "startingRecord": 0}},
        )
        return [self._summary(p) for p in parts]

    async def part(self, part_number: str) -> dict:
        parts = await self._post(
            "/search/partnumber",
            {"SearchByPartRequest": {"mouserPartNumber": part_number, "partSearchOptions": "Exact"}},
        )
        if not parts:
            raise LookupError(f"Mouser kender ikke '{part_number}'")
        # Foretræk et eksakt match på Mouser- eller producent-nummer
        wanted = part_number.casefold()
        p = next(
            (x for x in parts if wanted in (x.get("MouserPartNumber", "").casefold(), x.get("ManufacturerPartNumber", "").casefold())),
            parts[0],
        )
        return {
            **self._summary(p),
            "parameters": {a["AttributeName"]: a["AttributeValue"] for a in p.get("ProductAttributes") or []},
        }
