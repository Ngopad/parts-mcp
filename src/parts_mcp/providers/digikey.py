"""Lille klient til DigiKey Product Information v4 (2-legged OAuth, kun read)."""

import os
import time
from urllib.parse import quote

import httpx

from .common import TTLCache, summary


class DigiKeyClient:
    name = "digikey"

    @classmethod
    def from_env(cls) -> "DigiKeyClient | None":
        if os.getenv("DIGIKEY_CLIENT_ID") and os.getenv("DIGIKEY_CLIENT_SECRET"):
            return cls()
        return None

    def __init__(self) -> None:
        self.client_id = os.environ["DIGIKEY_CLIENT_ID"]
        self.client_secret = os.environ["DIGIKEY_CLIENT_SECRET"]
        self.currency = os.getenv("DIGIKEY_CURRENCY", "DKK")
        self.locale = {
            "X-DIGIKEY-Locale-Site": os.getenv("DIGIKEY_SITE", "DK"),
            "X-DIGIKEY-Locale-Language": os.getenv("DIGIKEY_LANGUAGE", "en"),
            "X-DIGIKEY-Locale-Currency": self.currency,
        }
        base_url = os.getenv("DIGIKEY_BASE_URL", "https://api.digikey.com")
        self._http = httpx.AsyncClient(base_url=base_url, timeout=30)
        self._token: str | None = None
        self._token_expires = 0.0
        self._cache = TTLCache()

    async def _get_token(self) -> str:
        # Genbrug tokenet indtil 60 sek. før det udløber
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        r = await self._http.post(
            "/v1/oauth2/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + int(data.get("expires_in", 600))
        return self._token

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        cache_key = f"{method} {path} {kwargs.get('json')}"
        if (hit := self._cache.get(cache_key)) is not None:
            return hit

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {await self._get_token()}",
                "X-DIGIKEY-Client-Id": self.client_id,
                **self.locale,
            }
            r = await self._http.request(method, path, headers=headers, **kwargs)
            if r.status_code == 401 and attempt == 0:
                self._token = None  # tokenet er udløbet/ugyldigt, hent et nyt
                continue
            r.raise_for_status()
            data = r.json()
            self._cache.set(cache_key, data)
            return data
        raise RuntimeError("unreachable")

    def _summary(self, p: dict) -> dict:
        # Vælg den variant med lavest minimumsantal (typisk cut tape) til priser
        variations = sorted(p.get("ProductVariations") or [], key=lambda v: v.get("MinimumOrderQuantity") or 0)
        v = variations[0] if variations else {}
        breaks = [{"qty": b["BreakQuantity"], "price": b["UnitPrice"]} for b in v.get("StandardPricing") or []]
        return summary(
            supplier=self.name,
            mpn=p.get("ManufacturerProductNumber"),
            manufacturer=(p.get("Manufacturer") or {}).get("Name"),
            description=(p.get("Description") or {}).get("ProductDescription"),
            supplier_pn=v.get("DigiKeyProductNumber"),
            # DigiKey udelader QuantityAvailable når lageret er 0
            in_stock=p.get("QuantityAvailable", sum(x.get("QuantityAvailableforPackageType") or 0 for x in variations)),
            price_breaks=breaks,
            currency=self.currency,
            url=p.get("ProductUrl"),
            datasheet=p.get("DatasheetUrl"),
        )

    async def search(self, keywords: str, limit: int = 10) -> list[dict]:
        data = await self._request(
            "POST",
            "/products/v4/search/keyword",
            json={"Keywords": keywords, "Limit": limit, "Offset": 0},
        )
        return [self._summary(p) for p in data.get("Products", [])]

    async def part(self, product_number: str) -> dict:
        try:
            data = await self._request("GET", f"/products/v4/search/{quote(product_number, safe='')}/productdetails")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            # F.eks. "Duplicate Products found" når flere producenter bruger samme MPN
            detail = e.response.json().get("detail") or "ikke fundet"
            raise LookupError(
                f"DigiKey: {detail}. Brug et DigiKey-nummer (f.eks. 497-1591-1-ND) fra digikey_search."
            ) from None
        p = data.get("Product", data)
        return {
            **self._summary(p),
            "parameters": {x["ParameterText"]: x["ValueText"] for x in p.get("Parameters") or []},
        }
