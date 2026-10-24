# parts-mcp

To MCP-servere i Docker, som du starter når du skal bruge dem. Virker ens på Windows og Linux.

| Server | Port | Hvad |
|---|---|---|
| `parts-mcp` | 8000 | Komponentsøgning hos DigiKey, Mouser, Farnell og jlcsearch (JLCPCB/LCSC). Octopart er fravalgt (for dyrt). |
| `kicad-mcp` | 3334 | [KiCad MCP Pro](https://github.com/oaslananka/kicad-mcp-pro) 4.4.0 med KiCad 10 indbygget (kicad-cli, ERC/DRC, BOM, eksport). |

## Leverandører

En leverandør slås kun til, hvis dens nøgler står i `.env` – ellers vises dens tools bare ikke.

| Leverandør | Nøgler i `.env` | Tools | Valuta |
|---|---|---|---|
| DigiKey | `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` | `digikey_search`, `digikey_part` | `DIGIKEY_CURRENCY` |
| Mouser | `MOUSER_API_KEY` | `mouser_search`, `mouser_part` | fra API'et |
| Farnell | `FARNELL_API_KEY` (+ `FARNELL_STORE`) | `farnell_search`, `farnell_part` | `FARNELL_CURRENCY` |
| jlcsearch | ingen – altid slået til | `jlc_search`, `jlc_part` (LCSC-nr., f.eks. `C7950`) | USD |

`search_all` søger hos alle slåede-til leverandører på én gang. Alle tools returnerer samme felter (`mpn`, `manufacturer`, `supplier_pn`, `in_stock`, `unit_price`, `price_breaks`, `url`, `datasheet` …), og `*_part` giver også `parameters`.

Kendte begrænsninger:
- **jlcsearch:** fritekstsøgningen returnerer pt. urelaterede dele ([tscircuit/jlcsearch#611](https://github.com/tscircuit/jlcsearch/issues/611)). Dem filtrerer `jlc_search` fra, så den giver få eller ingen resultater, indtil det er rettet. Opslag på LCSC-nummer med `jlc_part` virker.
- **DigiKey:** `digikey_part` med et producentnummer, som flere producenter bruger (f.eks. `LM358DT`), giver en fejl. Brug DigiKey-nummeret fra `digikey_search`.

## Struktur

```
src/parts_mcp/
  server.py              # FastMCP-server og tools
  providers/common.py    # cache, prisparsing, fælles resultatformat
  providers/digikey.py   # DigiKey (OAuth, token-fornyelse)
  providers/mouser.py    # Mouser
  providers/farnell.py   # Farnell/element14
  providers/jlcsearch.py # jlcsearch (JLCPCB/LCSC)
kicad/Dockerfile         # KiCad 10 + KiCad MCP Pro
projects/                # standard-mappe til KiCad-projekter (ikke i git)
```

Ny leverandør = ny fil i `providers/` med `from_env()`, `search()` og `part()`, + tools i `server.py`.

## Krav

Kun Docker med compose – Python og KiCad skal ikke installeres.

- **Linux:** Docker Engine + compose-plugin.
- **Windows:** Docker Desktop, eller Docker installeret i en WSL-distro (f.eks. Ubuntu). Med WSL sættes `wsl` foran kommandoerne, kørt fra repo-mappen i PowerShell – f.eks. `wsl docker compose up`.

## Første gang

1. **Nøgler:**
   - DigiKey: developer.digikey.com → organisation → ny app → abonnér på *Product Information v4* → kopiér client ID/secret.
   - Mouser: mouser.com → My Account → APIs → *Search API*.
   - Farnell: partner.element14.com → registrér → *Product Search API*.
2. Opret `.env` og udfyld den:
   ```
   cp .env.example .env        # Windows (PowerShell): copy .env.example .env
   ```
   - Nøgler til de leverandører, du vil bruge (se tabellen ovenfor)
   - `KICAD_MCP_AUTH_TOKEN`: en tilfældig streng på mindst 32 tegn
   - `KICAD_PROJECTS`: mappen med dine KiCad-projekter (standard `./projects`). Med Docker i WSL skal det være en WSL-sti, f.eks. `/mnt/c/Users/<dig>/Documents/KiCad`.
3. Kør startscriptet (se nedenfor). Første gang bygges imagerne (KiCad ca. 3,7 GB), der laves et KiCad-token i `.env`, og der skrives en `.mcp.json`, så Claude Code finder serverne.
4. Genindlæs VS Code / genstart Claude Code, og godkend `parts` og `kicad`.

## Brug

Startscriptet klarer det hele hver gang: tjekker `.env`, laver token og `.mcp.json`, finder Docker (Docker Desktop eller Docker i WSL), bygger og starter.

| | Windows | Linux |
|---|---|---|
| Begge servere | dobbeltklik `start.cmd` | `bash start.sh` |
| Kun komponentsøgning | dobbeltklik `start-parts.cmd` (eller `start.cmd parts`) | `bash start.sh parts` |
| Kun KiCad | `start.cmd kicad` | `bash start.sh kicad` |

Serverne kører i forgrunden: lad vinduet stå åbent, og stop med Ctrl+C eller ved at lukke det. På Windows med Docker i WSL er det nødvendigt – WSL lukker Ubuntu (og containerne) ned, når der ikke er en aktiv `wsl`-session.

`.env` og `.mcp.json` er i `.gitignore`. Del `.env` med kollegaer via en password manager, aldrig i git.

I Claude peger du KiCad MCP på et projekt med stien inde i containeren, f.eks. `/projects/mit-board`.

Tip: brug `DIGIKEY_BASE_URL=https://sandbox-api.digikey.com` med sandbox-nøgler under udvikling.

## Sikkerhed

Begge servere lytter kun på `127.0.0.1` og kan ikke nås fra netværket. `parts-mcp` har ingen login; `kicad-mcp` kræver token.

KiCad MCP Pro starter i `readonly`-tilstand. Sæt `KICAD_MCP_OPERATING_MODE=write` under `kicad-mcp` → `environment` i `docker-compose.yml`, hvis den skal kunne ændre filer.
