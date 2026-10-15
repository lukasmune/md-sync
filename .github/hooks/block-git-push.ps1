# preToolUse hook: deny terminal tool calls that run `git push`.
# Reads the hook payload (camelCase or VS Code snake_case) from stdin and writes
# one JSON decision object to stdout. This is a guard rail, not a security
# boundary: it inspects command text and cannot see indirect routes.

$ErrorActionPreference = 'Stop'

function Write-Decision([string]$decision, [string]$reason) {
    @{ permissionDecision = $decision; permissionDecisionReason = $reason } |
        ConvertTo-Json -Compress
}

function Deny([string]$reason) {
    Write-Decision 'deny' $reason
    exit 0
}

# Terminal-like tool names. Anything else is left to the default permission flow.
$ShellToolPattern = '(?i)(^|[^a-z])(powershell|pwsh|bash|sh|zsh|cmd|shell|terminal|run_in_terminal|runInTerminal)([^a-z]|$)'

# `git`, optional global options (-C/-c with value, --opt[=value], -p/-P), then `push`.
$Value = '(?:"[^"]*"|''[^'']*''|\S+)'
$GitPushPattern = '(?i)(?<![\w.-])git(?:\.exe)?["'']?(?:\s+(?:-[Cc]\s+' + $Value + '|--[\w-]+(?:=' + $Value + ')?|-[pP]))*\s+["'']?push\b'

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Deny 'git push guard: empty hook input could not be inspected.'
    }
    $payload = $raw | ConvertFrom-Json

    $toolName = $payload.toolName
    if (-not $toolName) { $toolName = $payload.tool_name }
    if (-not $toolName) {
        Deny 'git push guard: tool name missing from hook input.'
    }

    if ($toolName -notmatch $ShellToolPattern) {
        exit 0
    }

    $toolArgs = $payload.toolArgs
    if ($null -eq $toolArgs) { $toolArgs = $payload.tool_input }
    if ($null -eq $toolArgs) {
        Deny 'git push guard: terminal tool arguments missing from hook input.'
    }

    if ($toolArgs -is [string]) {
        $text = $toolArgs
    } else {
        $text = $toolArgs | ConvertTo-Json -Depth 20 -Compress
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        Deny 'git push guard: terminal tool arguments were empty.'
    }

    # Decode JSON escapes so quoted/escaped text is matched as typed.
    $decoded = [regex]::Unescape($text)

    if ($decoded -match $GitPushPattern -or $text -match $GitPushPattern) {
        Deny 'git push is blocked in this repository. Commit locally and ask the user to push.'
    }
    exit 0
} catch {
    Deny "git push guard: hook failed to inspect the tool call ($($_.Exception.Message))."
}
