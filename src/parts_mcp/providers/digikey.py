"""Lille klient til DigiKey Product Information v4 (2-legged OAuth, kun read)."""

import os
import time

import httpx

BASE_URL = os.getenv("DIGIKEY_BASE_URL", "https://api.digikey.com")
CACHE_SECONDS = int(os.getenv("CACHE_SECONDS", "3600"))


class DigiKeyClient:
    def __init__(self) -> None:
        self.client_id = os.environ["DIGIKEY_CLIENT_ID"]
        self.client_secret = os.environ["DIGIKEY_CLIENT_SECRET"]
        self.locale = {
            "X-DIGIKEY-Locale-Site": os.getenv("DIGIKEY_SITE", "DK"),
            "X-DIGIKEY-Locale-Language": os.getenv("DIGIKEY_LANGUAGE", "en"),
            "X-DIGIKEY-Locale-Currency": os.getenv("DIGIKEY_CURRENCY", "DKK"),
        }
        self._http = httpx.AsyncClient(base_url=BASE_URL, timeout=30)
        self._token: str | None = None
        self._token_expires = 0.0
        self._cache: dict[str, tuple[float, dict]] = {}

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
        hit = self._cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]

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
            self._cache[cache_key] = (time.time(), data)
            return data
        raise RuntimeError("unreachable")

    async def keyword_search(self, keywords: str, limit: int = 10) -> dict:
        return await self._request(
            "POST",
            "/products/v4/search/keyword",
            json={"Keywords": keywords, "Limit": limit, "Offset": 0},
        )

    async def product_details(self, product_number: str) -> dict:
        return await self._request(
            "GET", f"/products/v4/search/{httpx.URL(product_number)}/productdetails"
        )
