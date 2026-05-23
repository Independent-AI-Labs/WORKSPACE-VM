<#
.SYNOPSIS
    Run a single MTP benchmark completion request
.PARAMETER Port
    Server port. Default: 8080
.PARAMETER NPredict
    Number of tokens to generate. Default: 128
.PARAMETER Prompt
    Prompt text. Default: "Explain the architecture of a modern large language model"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [int]$Port = 8080,

    [Parameter(Mandatory = $false)]
    [int]$NPredict = 1024,

    [Parameter(Mandatory = $false)]
    [string]$Prompt = "The following is a detailed technical analysis of advanced computational systems. In the modern era of artificial intelligence, large language models have become increasingly important for a wide range of applications including natural language processing, code generation, scientific research, and creative writing. These models are trained on vast amounts of text data and use transformer architectures to generate coherent and contextually appropriate responses. The training process involves optimizing billions of parameters through gradient descent on carefully curated datasets. The resulting models can perform complex reasoning tasks, answer questions, write code, and engage in multi-turn conversations. Understanding how these systems work requires knowledge of machine learning, neural networks, optimization algorithms, and computational linguistics. The field continues to evolve rapidly with new techniques being developed to improve model efficiency, reduce training costs, and enhance the quality of generated outputs. Researchers are exploring methods such as mixture of experts, speculative decoding, and quantization to make these models more practical for deployment on consumer hardware. The implications of this technology extend far beyond simple text generation, affecting how we interact with computers, how we create content, and how we solve complex problems across many domains. As these models become more capable, it is important to consider both their potential benefits and their limitations. They can provide valuable assistance in many tasks but should not be relied upon as the sole source of truth for critical decisions. The development of these systems represents one of the most significant technological advances of the twenty-first century and will continue to shape the future of computing and artificial intelligence for years to come."
)

$ErrorActionPreference = "Stop"

$reqFile = Join-Path $env:TEMP "mtp-bench-req.json"
@{ prompt = $Prompt; n_predict = $NPredict } | ConvertTo-Json -Compress | Out-File -FilePath $reqFile -Encoding ASCII -NoNewline

Write-Host "Sending request (n_predict=$NPredict)..."
$r = Invoke-RestMethod -Uri "http://localhost:$Port/completion" -Method Post -ContentType "application/json" -InFile $reqFile

$pp = [math]::Round($r.timings.prompt_per_second, 2)
$tg = [math]::Round($r.timings.predicted_per_second, 2)
$draftN = $r.timings.draft_n
$draftAccepted = $r.timings.draft_n_accepted
$acceptRate = if ($draftN -gt 0) { [math]::Round($draftAccepted / $draftN * 100, 1) } else { 0 }

Write-Host "pp: $pp t/s"
Write-Host "tg: $tg t/s"
Write-Host "draft_n: $draftN"
Write-Host "draft_accepted: $draftAccepted ($acceptRate%)"
