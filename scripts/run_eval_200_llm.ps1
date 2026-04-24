param(
    [int]$TopK = 10,
    [string]$EvalSet = "data/eval/auto_eval_set.200.jsonl",
    [string]$Report = "data/eval/eval_report.llm.200.json",
    [int]$ManualSample = 50,
    [string]$ManualSampleFile = "data/eval/manual_off_topic_sample.200.jsonl"
)

$cmdArgs = @(
    "run", "-n", "llm",
    "python", "scripts/eval_rag_quality.py",
    "--eval-set", $EvalSet,
    "--regenerate",
    "--auto-generate", "200",
    "--top-k", "$TopK",
    "--check-answers",
    "--max-answer-queries", "200",
    "--manual-off-topic-sample", "$ManualSample",
    "--manual-off-topic-output", $ManualSampleFile,
    "--output", $Report
)

Write-Host "Running eval with args:"
Write-Host ("conda " + ($cmdArgs -join " "))
& conda @cmdArgs
exit $LASTEXITCODE
