param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BotArgs
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv312\Scripts\python.exe"

Push-Location $projectRoot
try {
    if (Test-Path $venvPython) {
        & $venvPython "main.py" @BotArgs
    }
    else {
        py -3.12 "main.py" @BotArgs
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
