param(
    [ValidateSet("test", "smoke", "sync", "export", "check", "help")]
    [string]$Command = "help"
)

& "$PSScriptRoot\md-sync.ps1" -Command $Command
exit $LASTEXITCODE