# KDD-Board Launcher (WebMCP, Blind Vault, Kanban UI)
$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $PSScriptRoot
$BoardDir = Join-Path $RepoDir "tools/kdd-board"

if (-not (Test-Path $BoardDir)) {
  $BoardDir = Join-Path (Split-Path -Parent $RepoDir) "kdd-board"
}

if (-not (Test-Path $BoardDir)) {
  Write-Error "No se encontró el directorio kdd-board en $BoardDir"
  exit 1
}

Write-Host "🚀 Iniciando KDD-Board para el proyecto: $RepoDir" -ForegroundColor Cyan
Set-Location -Path $BoardDir

if (-not (Test-Path "node_modules")) {
  Write-Host "📦 Instalando dependencias de kdd-board..." -ForegroundColor Yellow
  npm install
}

$env:KDD_PROJECT_DIR = $RepoDir
npm start
