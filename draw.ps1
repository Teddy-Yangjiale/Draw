$env:PYTHONPATH = "$PSScriptRoot;$env:PYTHONPATH"
if (Get-Command py -ErrorAction SilentlyContinue) {
    py -m pptdraw @args
} else {
    python -m pptdraw @args
}
