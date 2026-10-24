"""Komponent-MCP-server til Vermillion-teamet (DigiKey nu, flere leverandører senere)."""

import os

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext

from .providers.digikey import DigiKeyClient


def build_auth():
    """GitHub-login når GITHUB_CLIENT_ID er sat, ellers ingen auth (kun til lokal test)."""
    if not os.getenv("GITHUB_CLIENT_ID"):
        print("ADVARSEL: ingen auth slået til - brug kun lokalt!")
        return None
    from fastmcp.server.auth.providers.github import GitHubProvider

    return GitHubProvider(
        client_id=os.environ["GITHUB_CLIENT_ID"],
        client_secret=os.environ["GITHUB_CLIENT_SECRET"],
        base_url=os.environ["PUBLIC_URL"],  # f.eks. https://thinkcentre.xxx.ts.net
    )


class AllowListMiddleware(Middleware):
    """Kun GitHub-brugere i ALLOWED_GITHUB_USERS må kalde tools."""

    def __init__(self, allowed: set[str]) -> None:
        self.allowed = allowed

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        token = get_access_token()
        login = (token.claims.get("login") if token else None) or ""
        if login.lower() not in self.allowed:
            raise ToolError(f"GitHub-brugeren '{login}' har ikke adgang.")
        return await call_next(context)


auth = build_auth()
mcp = FastMCP("parts", auth=auth)
if auth:
    allowed = {u.strip().lower() for u in os.getenv("ALLOWED_GITHUB_USERS", "").split(",") if u.strip()}
    mcp.add_middleware(AllowListMiddleware(allowed))

digikey = DigiKeyClient()


def _summary(p: dict) -> dict:
    """Skær DigiKeys store svar ned til det vigtigste."""
    return {
        "mpn": p.get("ManufacturerProductNumber"),
        "manufacturer": (p.get("Manufacturer") or {}).get("Name"),
        "description": (p.get("Description") or {}).get("ProductDescription"),
        "unit_price": p.get("UnitPrice"),
        "in_stock": p.get("QuantityAvailable"),
        "digikey_numbers": [v.get("DigiKeyProductNumber") for v in p.get("ProductVariations") or []],
        "url": p.get("ProductUrl"),
        "datasheet": p.get("DatasheetUrl"),
    }


@mcp.tool
async def digikey_search(keywords: str, limit: int = 10) -> list[dict]:
    """Søg efter komponenter hos DigiKey, f.eks. '10k 0603 resistor' eller 'STM32F4'."""
    data = await digikey.keyword_search(keywords, min(limit, 50))
    return [_summary(p) for p in data.get("Products", [])]


@mcp.tool
async def digikey_part(product_number: str) -> dict:
    """Hent fulde detaljer (parametre, priser, lager) for et DigiKey- eller producent-partnummer."""
    data = await digikey.product_details(product_number)
    return data.get("Product", data)


def main() -> None:
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
