# Starter parts-mcp og kicad-mcp. Køres via start.cmd (dobbeltklik).
# Klarer selv token, .mcp.json og valg af Docker (Docker Desktop eller Docker i WSL).
#   start.cmd         -> begge servere
#   start.cmd parts   -> kun komponentsøgning
#   start.cmd kicad   -> kun KiCad
param([ValidateSet('alle', 'parts', 'kicad')][string]$Only = 'alle')

$ErrorActionPreference = 'Continue'
$services = @{ alle = @(); parts = @('parts-mcp'); kicad = @('kicad-mcp') }[$Only]
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$utf8 = New-Object System.Text.UTF8Encoding $false  # uden BOM, ellers kan Claude Code ikke læse .mcp.json

function Stop-WithError($msg) {
    Write-Host ""
    Write-Host "FEJL: $msg" -ForegroundColor Red
    exit 1
}

# 1. .env med nøglerne skal ligge i mappen
$envFile = Join-Path $root '.env'
if (-not (Test-Path $envFile)) {
    Stop-WithError "Filen .env mangler i $root`nHent den fra jeres password manager, og gem den som .env i denne mappe."
}
$lines = [System.Collections.Generic.List[string]]([IO.File]::ReadAllLines($envFile))
$cfg = @{}
foreach ($line in $lines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') { $cfg[$Matches[1]] = $Matches[2].Trim('"', "'") }
}

# 2. KiCad-token: lav et første gang (min. 32 tegn)
$token = $cfg['KICAD_MCP_AUTH_TOKEN']
if (-not $token -or $token.Length -lt 32) {
    $chars = [char[]]'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
    $i = $lines.FindIndex({ param($l) $l -match '^\s*KICAD_MCP_AUTH_TOKEN\s*=' })
    if ($i -ge 0) { $lines[$i] = "KICAD_MCP_AUTH_TOKEN=$token" } else { $lines.Add("KICAD_MCP_AUTH_TOKEN=$token") }
    [IO.File]::WriteAllText($envFile, ($lines -join "`n") + "`n", $utf8)
    Write-Host "Lavede et nyt KiCad-token i .env"
}

# 3. .mcp.json, så Claude Code finder serverne
$mcpJson = @"
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
"@
$mcpFile = Join-Path $root '.mcp.json'
$old = if (Test-Path $mcpFile) { [IO.File]::ReadAllText($mcpFile) } else { '' }
$mcpChanged = $old.Replace("`r`n", "`n").Trim() -ne $mcpJson.Replace("`r`n", "`n").Trim()
if ($mcpChanged) { [IO.File]::WriteAllText($mcpFile, $mcpJson.Replace("`r`n", "`n") + "`n", $utf8) }

# Standardmappen til KiCad-projekter
if (-not $cfg['KICAD_PROJECTS'] -or $cfg['KICAD_PROJECTS'] -eq './projects') {
    New-Item -ItemType Directory -Force (Join-Path $root 'projects') | Out-Null
}

# 4. Find Docker: Docker Desktop først, ellers Docker i WSL
$docker = $null
if (Get-Command docker -ErrorAction SilentlyContinue) {
    cmd /c "docker info >nul 2>&1"
    if ($LASTEXITCODE -eq 0) { $docker = 'desktop' }
}
if (-not $docker -and (Get-Command wsl -ErrorAction SilentlyContinue)) {
    cmd /c "wsl docker info >nul 2>&1"
    if ($LASTEXITCODE -eq 0) { $docker = 'wsl' }
}
if (-not $docker) {
    Stop-WithError "Kan ikke finde en kørende Docker.`nStart Docker Desktop (eller installér Docker i WSL), og prøv igen."
}

# Oversigt
$suppliers = @()
if ($cfg['DIGIKEY_CLIENT_ID'] -and $cfg['DIGIKEY_CLIENT_SECRET']) { $suppliers += 'DigiKey' }
if ($cfg['MOUSER_API_KEY']) { $suppliers += 'Mouser' }
if ($cfg['FARNELL_API_KEY']) { $suppliers += 'Farnell' }
$suppliers += 'JLCPCB/LCSC'
Write-Host ""
Write-Host "Leverandører: $($suppliers -join ', ')"
Write-Host "Docker: $(if ($docker -eq 'wsl') { 'Docker i WSL' } else { 'Docker Desktop' })"
if ($mcpChanged) {
    Write-Host ""
    Write-Host ".mcp.json er opdateret. Genindlæs VS Code (Ctrl+Shift+P -> Developer: Reload Window)," -ForegroundColor Yellow
    Write-Host "når serverne kører, og godkend 'parts' og 'kicad'." -ForegroundColor Yellow
}
Write-Host ""
$what = @{ alle = 'komponentsøgning og KiCad'; parts = 'kun komponentsøgning'; kicad = 'kun KiCad' }[$Only]
Write-Host "Starter $what." -ForegroundColor Cyan
if ($Only -ne 'parts') { Write-Host "Første gang hentes KiCad (ca. 3,7 GB), så det kan tage flere minutter." -ForegroundColor Cyan }
Write-Host "Klar når der står 'Uvicorn running'. LAD VINDUET STÅ ÅBENT - lukker du det, stopper serverne." -ForegroundColor Cyan
Write-Host ""

# 5. Byg (hurtigt når intet er ændret) og start i forgrunden
if ($docker -eq 'wsl') { wsl docker compose up --build @services } else { docker compose up --build @services }
