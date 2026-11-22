<#
getbuild.ps1: install an official SolidCraft release into this lane's own builds folder and run it with an isolated
profile (kit v2.37, docs/reproducing.md "Builds"). Windows; Linux and macOS lanes use getbuild.sh.

  kit\getbuild.ps1 ensure [latest|newest|rc|nightly|<version>]  install if missing; prints SOLIDCRAFT_BUILD= and SOLIDCRAFT_CLI=
  kit\getbuild.ps1 run <which> <cli args...>                    ensure, then run solidcraft-cli with the isolated profile
                                                                (no `--` before the args: powershell -File refuses it)
  kit\getbuild.ps1 env <which>                                  ensure, then print $env: lines (CLI, app, profile)
  kit\getbuild.ps1 list                                         installed versions
  kit\getbuild.ps1 prune [keep]                                 delete all but the newest <keep> (default 4) installs

latest = newest non-prerelease (the current release), newest = newest of all (rc or nightly included),
rc / nightly = newest of that kind, <version> = exactly that release (0.45.0-rc.3 or v0.45.0-rc.3).
Folders: $env:SC_BUILDS_DIR (default <kit>\builds)\upstream-<version>\ and profile-<version>\{settings,recovery,localappdata}.
Only tangency-labs/solidcraft releases; the asset's sha256 must match GitHub's digest (or the release's SHA256SUMS.txt).
Downloads land in a fresh folder and are extracted by kit\safe_extract.py (python -I) into another fresh, empty folder.
Nothing outside the builds folder is written.
#>
# A plain (not advanced) param block, so CLI flags like --version after `run <which>` land in $args.
param([string]$Cmd = "", [string]$Which = "latest")
$Rest = @($args)
$ErrorActionPreference = "Stop"
$Repo = "tangency-labs/solidcraft"
$Kit = Split-Path -Parent $PSScriptRoot
$Builds = if ($env:SC_BUILDS_DIR) { $env:SC_BUILDS_DIR } else { Join-Path $Kit "builds" }
$VerRe = '^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z]+(\.[0-9A-Za-z]+)*)?$'

function Die([string]$msg) { [Console]::Error.WriteLine("getbuild: $msg"); exit 1 }
function Note([string]$msg) { [Console]::Error.WriteLine("getbuild: $msg") }

function Invoke-Gh([string[]]$a) {
    $out = & gh @a
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($out -join "`n")
}

function Resolve-Tag([string]$w) {
    # jq strings with double quotes do not survive Windows PowerShell 5.1's native argument passing: filter here instead
    if ($w -eq "latest") { return Invoke-Gh @("api", "repos/$Repo/releases/latest", "--jq", ".tag_name") }
    if (@("newest", "rc", "nightly") -notcontains $w) {
        $v = $w -replace '^v', ''
        if ($v -notmatch $VerRe) { Die "not a version or keyword: $w" }
        return "v$v"
    }
    $json = Invoke-Gh @("api", "repos/$Repo/releases?per_page=30")
    if ($null -eq $json) { Die "could not list releases of $Repo" }
    $all = $json | ConvertFrom-Json
    $rels = $all | Where-Object { -not $_.draft }
    if ($w -eq "rc") { $rels = $rels | Where-Object { $_.tag_name -match '-rc\.' } }
    if ($w -eq "nightly") { $rels = $rels | Where-Object { $_.tag_name -match '-nightly\.' } }
    $top = $rels | Sort-Object { [datetime]$_.published_at } | Select-Object -Last 1
    if ($top) { return $top.tag_name }
    return $null
}

function Find-Cli([string]$dir) {
    Get-ChildItem -LiteralPath $dir -Recurse -File -Filter "solidcraft-cli.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Find-Python {
    foreach ($p in @($env:SC_PYTHON, "python", "py")) {
        if (-not $p) { continue }
        try {
            & $p -I -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $p }
        } catch {}
    }
    Die "no Python 3.11+ found (set SC_PYTHON)"
}

function Ensure([string]$w) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Die "gh (GitHub CLI) is required" }
    $tag = Resolve-Tag $w
    if (-not $tag) { Die "no release matches '$w' in $Repo" }
    $ver = $tag.Trim() -replace '^v', ''
    if ($ver -notmatch $VerRe) { Die "unexpected tag from ${Repo}: $tag" }
    $tag = "v$ver"
    $dest = Join-Path $Builds "upstream-$ver"
    if (Test-Path -LiteralPath (Join-Path $dest ".getbuild.json")) {
        $cli = Find-Cli $dest
        if ($cli) {
            Note "$ver already installed in $dest"
            return @{ Build = $dest; Cli = $cli.FullName; Version = $ver }
        }
    }
    if (Test-Path -LiteralPath $dest) { Die "$dest exists but was not installed by getbuild: move it aside or delete it yourself" }

    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $asset = "solidcraft-$ver-windows-$arch-portable.zip"
    $json = Invoke-Gh @("api", "repos/$Repo/releases/tags/$tag")
    if ($null -eq $json) { Die "release $tag not found in $Repo" }
    $rel = $json | ConvertFrom-Json
    if ($rel.draft) { Die "$tag is a draft release" }
    $a = @($rel.assets) | Where-Object { $_.name -ceq $asset } | Select-Object -First 1
    if (-not $a) { Die "release $tag in $Repo has no asset $asset" }
    $info = if ($a.digest) { [string]$a.digest } else { "none" }

    New-Item -ItemType Directory -Force -Path $Builds | Out-Null
    $stamp = [guid]::NewGuid().ToString("N").Substring(0, 8)
    $dl = New-Item -ItemType Directory -Path (Join-Path $Builds ".dl-$ver-$stamp")
    $x = New-Item -ItemType Directory -Path (Join-Path $Builds ".x-$ver-$stamp")
    try {
        Note "downloading $asset from $Repo $tag"
        & gh release download $tag -R $Repo -p $asset -D $dl.FullName | Out-Null
        if ($LASTEXITCODE -ne 0) { Die "download failed" }
        $file = Join-Path $dl.FullName $asset
        $got = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower()
        $expected = $null; $how = "none listed"
        if ($info.StartsWith("sha256:")) {
            $expected = $info.Substring(7).ToLower(); $how = "GitHub asset digest"
        } else {
            & gh release download $tag -R $Repo -p "SHA256SUMS.txt" -D $dl.FullName 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                foreach ($line in Get-Content -LiteralPath (Join-Path $dl.FullName "SHA256SUMS.txt")) {
                    $parts = $line -split '\s+', 2
                    if ($parts.Count -eq 2 -and $parts[1].TrimStart('*') -eq $asset) { $expected = $parts[0].ToLower(); break }
                }
                if ($expected) { $how = "the release's SHA256SUMS.txt" }
            }
        }
        if ($expected) {
            if ($got -ne $expected) { Die "sha256 mismatch for ${asset}: got $got, $how says $expected. Not installed." }
            Note "sha256 matches $how"
        } else {
            Note "WARNING: GitHub lists no digest for $asset; installed unverified (sha256 $got)"
        }
        $py = Find-Python
        & $py -I (Join-Path $Kit "kit\safe_extract.py") $file $x.FullName | ForEach-Object { Note $_ }
        if ($LASTEXITCODE -ne 0) { Die "extract refused or failed" }
        if (-not (Find-Cli $x.FullName)) { Die "no solidcraft-cli.exe in $asset" }
        $meta = [ordered]@{ tag = $tag; asset = $asset; sha256 = $got; verified_by = $how; installed_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") }
        [IO.File]::WriteAllText((Join-Path $x.FullName ".getbuild.json"), ($meta | ConvertTo-Json -Compress) + "`n")
        try {
            Move-Item -LiteralPath $x.FullName -Destination $dest
        } catch {
            if (-not (Test-Path -LiteralPath (Join-Path $dest ".getbuild.json"))) { Die "could not move the build into $dest" }
            Note "another run installed $ver first; using it"
        }
    } finally {
        foreach ($d in @($dl.FullName, $x.FullName)) {
            if (Test-Path -LiteralPath $d) { Remove-Item -LiteralPath $d -Recurse -Force }
        }
    }
    Note "installed $ver in $dest"
    return @{ Build = $dest; Cli = (Find-Cli $dest).FullName; Version = $ver }
}

function Profile-Env([string]$ver) {
    $p = Join-Path $Builds "profile-$ver"
    $vars = [ordered]@{
        SOLIDCRAFT_SETTINGS_DIR = Join-Path $p "settings"
        SOLIDCRAFT_RECOVERY_DIR = Join-Path $p "recovery"
        LOCALAPPDATA            = Join-Path $p "localappdata"
    }
    foreach ($v in $vars.Values) { New-Item -ItemType Directory -Force -Path $v | Out-Null }
    return $vars
}

function Version-Key([string]$v) {
    # 0.45.0 > 0.45.0-rc.3 > 0.45.0-rc.2 > 0.45.0-nightly...; numbers compare as numbers
    $m = [regex]::Match($v, '^(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z]+)\.?([\d.]*))?')
    $kind = if (-not $m.Groups[4].Success) { 3 } elseif ($m.Groups[4].Value -eq "rc") { 2 } else { 1 }
    $tail = ($m.Groups[5].Value -split '\.' | Where-Object { $_ } | ForEach-Object { "{0:D12}" -f [int64]$_ }) -join "."
    return "{0:D6}.{1:D6}.{2:D6}.{3}.{4}" -f [int]$m.Groups[1].Value, [int]$m.Groups[2].Value, [int]$m.Groups[3].Value, $kind, $tail
}

function Installed {
    if (-not (Test-Path -LiteralPath $Builds)) { return @() }
    Get-ChildItem -LiteralPath $Builds -Directory -Filter "upstream-*" |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName ".getbuild.json") } |
        Sort-Object { Version-Key ($_.Name -replace '^upstream-', '') } -Descending
}

switch ($Cmd) {
    "ensure" {
        $b = Ensure $Which
        "SOLIDCRAFT_BUILD=$($b.Build)"
        "SOLIDCRAFT_CLI=$($b.Cli)"
    }
    "env" {
        $b = Ensure $Which
        "`$env:SOLIDCRAFT_CLI = '$($b.Cli)'"
        $app = Get-ChildItem -LiteralPath $b.Build -Recurse -File -Filter "solidcraft.exe" | Select-Object -First 1
        if ($app) { "`$env:SOLIDCRAFT_APP = '$($app.FullName)'" }
        $vars = Profile-Env $b.Version
        foreach ($k in $vars.Keys) { "`$env:$k = '$($vars[$k])'" }
    }
    "run" {
        $b = Ensure $Which
        $args2 = @($Rest | Where-Object { $_ -ne "--" })
        $vars = Profile-Env $b.Version
        $saved = @{}
        foreach ($k in $vars.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); Set-Item -Path "env:$k" -Value $vars[$k] }
        try {
            & $b.Cli @args2
            $code = $LASTEXITCODE
        } finally {
            foreach ($k in $saved.Keys) {
                if ($null -eq $saved[$k]) { Remove-Item -Path "env:$k" -ErrorAction SilentlyContinue } else { Set-Item -Path "env:$k" -Value $saved[$k] }
            }
        }
        exit $code
    }
    "list" {
        foreach ($d in Installed) { "$($d.Name -replace '^upstream-', '')  $(Get-Content -Raw -LiteralPath (Join-Path $d.FullName '.getbuild.json'))".TrimEnd() }
    }
    "prune" {
        $keep = 4
        if ($Which -ne "latest") { if ($Which -notmatch '^\d+$') { Die "keep must be a number" }; $keep = [int]$Which }
        Installed | Select-Object -Skip $keep | ForEach-Object {
            $v = $_.Name -replace '^upstream-', ''
            Note "removing $v"
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
            $p = Join-Path $Builds "profile-$v"
            if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
        }
    }
    default {
        Get-Content -LiteralPath $PSCommandPath -TotalCount 18 | Select-Object -Skip 1
        if ($Cmd) { exit 2 }
    }
}
