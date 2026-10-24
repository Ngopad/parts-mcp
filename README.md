# parts-mcp

MCP-server til komponentsøgning for Vermillion-teamet. Kører på ThinkCentre i Docker og eksponeres via Tailscale Funnel.

Leverandører: **DigiKey** (read, 2-legged OAuth). Planlagt: Mouser, Farnell, LCSC, Octopart.

## Struktur

```
src/parts_mcp/
  server.py              # FastMCP-server, tools, GitHub-login + allowlist
  providers/digikey.py   # DigiKey-klient (token-fornyelse + cache)
```

Ny leverandør = ny fil i `providers/` + tools i `server.py` (f.eks. `mouser_search`).

## Lokal test (Windows)

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .
copy .env.example .env      # udfyld DIGIKEY_*, lad GITHUB_CLIENT_ID stå tom
```

Start serveren (uden login, kun lokalt) og tilføj den til Claude Code:

```
.venv\Scripts\parts-mcp
claude mcp add --transport http parts http://localhost:8000/mcp
```

Tip: brug `DIGIKEY_BASE_URL=https://sandbox-api.digikey.com` med sandbox-nøgler under udvikling.

## Opsætning af nøgler

1. **DigiKey:** developer.digikey.com → organisation → ny app → abonnér på *Product Information v4* → kopiér client ID/secret.
2. **GitHub-login:** GitHub → Settings → Developer settings → OAuth Apps → New:
   - Homepage URL: `https://thinkcentre.<tailnet>.ts.net`
   - Callback URL: `https://thinkcentre.<tailnet>.ts.net/auth/callback`
3. Sæt `ALLOWED_GITHUB_USERS` til teamets GitHub-brugernavne.

## Deploy på ThinkCentre

```
git clone <repo> ~/parts-mcp && cd ~/parts-mcp
cp .env.example .env && nano .env
docker compose up -d --build
sudo tailscale funnel --bg 8000
```

Teamet tilføjer så `https://thinkcentre.<tailnet>.ts.net/mcp` under claude.ai → Settings → Connectors.
