[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectName = "xassemble-smoke-$([Guid]::NewGuid().ToString('N').Substring(0, 8))"
$secret = "smoke-test-secret-key-that-is-longer-than-thirty-two-characters"
$previousSecret = $env:XASSEMBLE_SECRET_KEY
$previousHost = $env:XASSEMBLE_HOST
$env:XASSEMBLE_SECRET_KEY = $secret
$env:XASSEMBLE_HOST = "http://localhost"

try {
    docker compose --project-name $projectName up --detach --build --wait xassemble
    $containerId = docker compose --project-name $projectName ps --quiet xassemble
    if (-not $containerId) { throw "The xassemble container did not start." }

    $health = docker inspect --format "{{.State.Health.Status}}" $containerId
    if ($health -ne "healthy") { throw "Unexpected container health: $health" }

    $frontend = docker compose --project-name $projectName exec -T xassemble python -c "import urllib.request; print('xassemble' in urllib.request.urlopen('http://127.0.0.1:8000/').read().decode().lower())"
    if ($frontend.Trim() -ne "True") { throw "The built frontend was not served." }

    docker compose --project-name $projectName exec -T xassemble python -c "from xassemble.database import Database; Database('/data/xassemble.sqlite3').create_document_set('smoke-marker', 'Smoke Marker')"
    docker compose --project-name $projectName restart xassemble
    docker compose --project-name $projectName up --detach --wait xassemble
    $marker = docker compose --project-name $projectName exec -T xassemble python -c "from xassemble.database import Database; print(Database('/data/xassemble.sqlite3').get_document_set('smoke-marker')['name'])"
    if ($marker.Trim() -ne "Smoke Marker") { throw "SQLite data did not survive restart." }

    Write-Host "Container startup, health, and SQLite persistence checks passed."
}
finally {
    docker compose --project-name $projectName down --volumes --remove-orphans
    if ($null -eq $previousSecret) {
        Remove-Item Env:XASSEMBLE_SECRET_KEY -ErrorAction SilentlyContinue
    } else {
        $env:XASSEMBLE_SECRET_KEY = $previousSecret
    }
    if ($null -eq $previousHost) {
        Remove-Item Env:XASSEMBLE_HOST -ErrorAction SilentlyContinue
    } else {
        $env:XASSEMBLE_HOST = $previousHost
    }
}
