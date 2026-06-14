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

# Put the project venv on PATH (not just hand its python.exe to the orchestrator):
# orchestrate.py shells `bash scripts/ci.sh`, which calls bare `python -m ruff/
# pytest/mypy`. Without the venv on PATH those resolve to system python — which
# lacks the tools, so ci.sh SKIPS every check and passes falsely green. On PATH,
# the tools are found and pytest imports the worktree's source via cwd.
$venvScripts = Join-Path $repo ".venv\Scripts"
if (Test-Path $venvScripts) {
  $env:PATH = "$venvScripts;$env:PATH"
  $py = Join-Path $venvScripts "python.exe"
  # The BMAD agent activation runs `python3 …`; on Windows that hits the Store
  # App-Execution-Alias stub ("Python was not found") and fails on the first try
  # every phase. Make `python3` resolve to the venv interpreter (a copy of
  # python.exe; Git Bash finds it on PATH ahead of the WindowsApps stub).
  $py3 = Join-Path $venvScripts "python3.exe"
  if ((Test-Path $py) -and -not (Test-Path $py3)) {
    Copy-Item $py $py3
    Write-Host "Created python3.exe shim in the venv."
  }
} else {
  Write-Host "WARNING: no .venv at $venvScripts — ci.sh may skip checks (false green)."
  $py = "python"
}

$pyArgs = @((Join-Path $here "orchestrate.py"))
if ($Once)   { $pyArgs += "--once" }
if ($DryRun) { $pyArgs += "--dry-run" }

Write-Host "Launching orchestrator: $py $($pyArgs -join ' ')"
& $py @pyArgs
exit $LASTEXITCODE
