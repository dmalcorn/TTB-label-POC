# auto-run/run.ps1 — launch the overnight orchestrator on Windows.
#
#   pwsh auto-run/run.ps1            # run until done / failure / cap
#   pwsh auto-run/run.ps1 -Once      # one story then stop (first supervised run)
#   pwsh auto-run/run.ps1 -DryRun    # show the plan, call nothing
#
# Forces the Claude subscription session by clearing any API key/token in this
# process so the headless CLI cannot silently bill an API key instead.

param(
  [switch]$Once,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $here

# Force subscription auth.
$env:ANTHROPIC_API_KEY = $null
$env:ANTHROPIC_AUTH_TOKEN = $null

# Pick the project venv python if present, else system python.
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$pyArgs = @((Join-Path $here "orchestrate.py"))
if ($Once)   { $pyArgs += "--once" }
if ($DryRun) { $pyArgs += "--dry-run" }

Write-Host "Launching orchestrator: $py $($pyArgs -join ' ')"
& $py @pyArgs
exit $LASTEXITCODE
