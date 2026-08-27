[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$Query,

    [ValidateRange(1, 20)]
    [int]$Limit = 5,

    [ValidateSet("hash", "ollama", "auto")]
    [string]$EmbeddingProvider = "hash"
)

# Hot-path only: this wrapper deliberately exposes no index-build or validation switches.
$indexScript = Join-Path $PSScriptRoot "vector_memory_index.py"
& python $indexScript --query $Query --limit $Limit --embedding-provider $EmbeddingProvider --pretty
exit $LASTEXITCODE
