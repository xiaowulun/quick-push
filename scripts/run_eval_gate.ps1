param(
    [string]$Baseline = "data/eval/eval_report.manual.2026-04-19.json",
    [string]$Candidate = "data/eval/eval_report.manual.v2.json",
    [double]$MinRecallDelta = 0.0,
    [double]$MinHit1Delta = 0.0,
    [double]$MinRerankEffectiveRate = 0.5
)

$cmdArgs = @(
    "run", "-n", "llm",
    "python", "scripts/check_eval_regression.py",
    "--baseline", $Baseline,
    "--candidate", $Candidate,
    "--min-recall-delta", "$MinRecallDelta",
    "--min-hit1-delta", "$MinHit1Delta",
    "--min-rerank-effective-rate", "$MinRerankEffectiveRate"
)

Write-Host "Running eval gate with args:"
Write-Host ("conda " + ($cmdArgs -join " "))
& conda @cmdArgs
exit $LASTEXITCODE

