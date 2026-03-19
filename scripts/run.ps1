param(
  [int]$Port = 8140
)

$env:PORT = "$Port"
Write-Host "Starting Fin-Sight on http://127.0.0.1:$Port"
python api.py

