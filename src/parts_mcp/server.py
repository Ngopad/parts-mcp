"""Komponent-MCP-server (DigiKey, Mouser, Farnell, jlcsearch). Kører lokalt i Docker."""

import asyncio
import os

from fastmcp import FastMCP

from .providers.digikey import DigiKeyClient
from .providers.farnell import FarnellClient
from .providers.jlcsearch import JlcSearchClient
from .providers.mouser import MouserClient

# Ingen auth: containeren er kun bundet til localhost (se docker-compose.yml)
mcp = FastMCP("parts")

# Kun leverandører med nøgler i .env bliver slået til
clients = {
    c.name: c
    for c in (DigiKeyClient.from_env(), MouserClient.from_env(), FarnellClient.from_env(), JlcSearchClient.from_env())
    if c
}
print("Leverandører slået til:", ", ".join(clients) or "ingen")


def _limit(limit: int) -> int:
    return max(1, min(limit, 50))


if digikey := clients.get("digikey"):

    @mcp.tool
    async def digikey_search(keywords: str, limit: int = 10) -> list[dict]:
        """Søg efter komponenter hos DigiKey, f.eks. '10k 0603 resistor' eller 'STM32F4'."""
        return await digikey.search(keywords, _limit(limit))

    @mcp.tool
    async def digikey_part(product_number: str) -> dict:
        """Hent detaljer (parametre, priser, lager) for et DigiKey- eller producent-partnummer."""
        return await digikey.part(product_number)


if mouser := clients.get("mouser"):

    @mcp.tool
    async def mouser_search(keywords: str, limit: int = 10) -> list[dict]:
        """Søg efter komponenter hos Mouser, f.eks. '10k 0603 resistor' eller 'STM32F4'."""
        return await mouser.search(keywords, _limit(limit))

    @mcp.tool
    async def mouser_part(part_number: str) -> dict:
        """Hent detaljer (parametre, priser, lager) for et Mouser- eller producent-partnummer."""
        return await mouser.part(part_number)


if farnell := clients.get("farnell"):

    @mcp.tool
    async def farnell_search(keywords: str, limit: int = 10) -> list[dict]:
        """Søg efter komponenter hos Farnell, f.eks. '10k 0603 resistor' eller 'STM32F4'."""
        return await farnell.search(keywords, _limit(limit))

    @mcp.tool
    async def farnell_part(part_number: str) -> dict:
        """Hent detaljer (parametre, priser, lager) for et Farnell-varenummer eller producent-partnummer."""
        return await farnell.part(part_number)


if jlc := clients.get("jlcsearch"):

    @mcp.tool
    async def jlc_search(keywords: str, limit: int = 10) -> list[dict]:
        """Søg i JLCPCB/LCSC-lagerkataloget (via jlcsearch). Priser i USD.

        Bemærk: jlcsearch' fritekstsøgning er pt. ustabil, så der kan komme få eller ingen resultater.
        Brug hellere jlc_part med et LCSC-nummer, hvis du har det.
        """
        return await jlc.search(keywords, _limit(limit))

    @mcp.tool
    async def jlc_part(lcsc_number: str) -> dict:
        """Hent pris, lager og pakke for et LCSC-nummer, f.eks. 'C7950'. Viser også om det er en JLC basic-del."""
        return await jlc.part(lcsc_number)


@mcp.tool
async def search_all(keywords: str, limit: int = 5) -> dict:
    """Søg hos alle slåede-til leverandører på én gang og sammenlign lager og priser.

    Giver {leverandør: [resultater]} eller {leverandør: {"error": ...}} hvis en leverandør fejler.
    """
    names = list(clients)
    results = await asyncio.gather(
        *(clients[n].search(keywords, _limit(limit)) for n in names), return_exceptions=True
    )
    return {n: {"error": str(r)} if isinstance(r, Exception) else r for n, r in zip(names, results)}


def main() -> None:
    # 0.0.0.0 inde i containeren; porten publiceres kun på 127.0.0.1 på værten
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
