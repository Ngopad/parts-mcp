#!/usr/bin/env bash
# Starter parts-mcp og kicad-mcp på Linux. Klarer selv token og .mcp.json.
#   bash start.sh         -> begge servere
#   bash start.sh parts   -> kun komponentsøgning
#   bash start.sh kicad   -> kun KiCad
set -u
cd "$(dirname "$0")"

fail() { printf '\nFEJL: %s\n' "$1" >&2; exit 1; }

case "${1:-alle}" in
    alle) services=""; what="komponentsøgning og KiCad" ;;
    parts) services="parts-mcp"; what="kun komponentsøgning" ;;
    kicad) services="kicad-mcp"; what="kun KiCad" ;;
    *) fail "Ukendt valg '$1'. Brug: bash start.sh [parts|kicad]" ;;
esac

# 1. .env med nøglerne skal ligge i mappen
[ -f .env ] || fail "Filen .env mangler i $(pwd). Hent den fra jeres password manager, og gem den som .env i denne mappe."

get() { grep -E "^[[:space:]]*$1[[:space:]]*=" .env | tail -1 | cut -d= -f2- | tr -d "\"' \r"; }

# 2. KiCad-token: lav et første gang (min. 32 tegn)
token=$(get KICAD_MCP_AUTH_TOKEN)
if [ ${#token} -lt 32 ]; then
    token=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)
    if grep -qE '^[[:space:]]*KICAD_MCP_AUTH_TOKEN[[:space:]]*=' .env; then
        sed -i "s|^[[:space:]]*KICAD_MCP_AUTH_TOKEN[[:space:]]*=.*|KICAD_MCP_AUTH_TOKEN=$token|" .env
    else
        printf '\nKICAD_MCP_AUTH_TOKEN=%s\n' "$token" >> .env
    fi
    echo "Lavede et nyt KiCad-token i .env"
fi

# 3. .mcp.json, så Claude Code finder serverne
new_mcp=$(cat <<EOF
{
  "mcpServers": {
    "parts": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    },
    "kicad": {
      "type": "http",
      "url": "http://localhost:3334/mcp",
      "headers": {
        "Authorization": "Bearer $token"
      }
    }
  }
}
EOF
)
mcp_changed=0
if [ "$(cat .mcp.json 2>/dev/null)" != "$new_mcp" ]; then
    printf '%s\n' "$new_mcp" > .mcp.json
    mcp_changed=1
fi

# Standardmappen til KiCad-projekter
projects=$(get KICAD_PROJECTS)
if [ -z "$projects" ] || [ "$projects" = "./projects" ]; then mkdir -p projects; fi

# 4. Docker skal køre
command -v docker >/dev/null || fail "Docker er ikke installeret."
docker info >/dev/null 2>&1 || fail "Docker kører ikke (eller din bruger mangler adgang - prøv: sudo usermod -aG docker \$USER, og log ind igen)."

# Oversigt
suppliers=""
[ -n "$(get DIGIKEY_CLIENT_ID)" ] && [ -n "$(get DIGIKEY_CLIENT_SECRET)" ] && suppliers="$suppliers DigiKey,"
[ -n "$(get MOUSER_API_KEY)" ] && suppliers="$suppliers Mouser,"
[ -n "$(get FARNELL_API_KEY)" ] && suppliers="$suppliers Farnell,"
echo
echo "Leverandører:$suppliers JLCPCB/LCSC"
if [ "$mcp_changed" = 1 ]; then
    echo
    echo ".mcp.json er opdateret. Genstart Claude Code, når serverne kører, og godkend 'parts' og 'kicad'."
fi
echo
echo "Starter $what."
[ "${1:-alle}" != parts ] && echo "Første gang hentes KiCad (ca. 3,7 GB), så det kan tage flere minutter."
echo "Klar når der står 'Uvicorn running'. Ctrl+C stopper serverne."
echo

# 5. Byg (hurtigt når intet er ændret) og start i forgrunden
# shellcheck disable=SC2086 # $services skal splittes (tom = alle)
exec docker compose up --build $services
