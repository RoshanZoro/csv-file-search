# search_kb.ps1
param(
    [Parameter(Position=0, Mandatory=$true)] [string]$Query,
    [string]$Section     = "",
    [switch]$CommandOnly,
    [switch]$StepsOnly,
    [int]   $MaxResults  = 15,
    [string]$CsvPath     = ""
)

if (-not $CsvPath) { $CsvPath = Join-Path $PSScriptRoot "knowledge_base.csv" }
if (-not (Test-Path $CsvPath)) { $CsvPath = "knowledge_base.csv" }
if (-not (Test-Path $CsvPath)) {
    Write-Host "`n  [ERROR] knowledge_base.csv not found." -ForegroundColor Red; exit 1
}

# ── Synonym map ───────────────────────────────────────────────────────────────
# Used ONLY as a fallback when a term doesn't hit the content directly.
# Synonyms are NOT used to match content on their own — they only help
# when the raw term is absent from the text.
$SynMap = @{
    "add"="create,new,install,useradd,adduser,join,setup"
    "create"="add,new,make,setup,useradd"
    "remove"="delete,del,uninstall,userdel"
    "delete"="remove,del,uninstall,userdel"
    "install"="add,setup,deploy,enable,dnf,apt"
    "join"="connect,add,domain,member,client,computer,desktop,pc"
    "desktop"="pc,computer,client,workstation,machine,join,windows,domain"
    "pc"="desktop,computer,client,workstation,machine"
    "computer"="pc,desktop,client,workstation,join,domain"
    "client"="pc,desktop,computer,workstation,join,domain,windows"
    "domain"="ad,active,directory,forest,dc,join,client,computer,bmc"
    "active"="ad,directory,domain,adds,windows"
    "directory"="ad,active,domain,adds,aduc,adac"
    "user"="users,account,useradd,adduser,userdel,usermod"
    "group"="groups,groupadd,groupmod,groupdel"
    "password"="passwd,pwd,pass,secret,chage,credentials"
    "show"="display,list,view,check,get,verify"
    "lock"="disable,block,usermod"
    "unlock"="enable,unblock,usermod"
    "interface"="int,port,fa,gi,eth,fastethernet,gigabit,nic"
    "vlan"="virtual,network,lan,trunk,access,switchport"
    "trunk"="uplink,inter,vlan,allowed"
    "router"="routing,route,ospf,rip,gateway"
    "routing"="route,ospf,rip,router,static"
    "subnet"="subnetting,cidr,mask,prefix,network,ip,vlsm"
    "subnetting"="subnet,cidr,mask,vlsm,prefix,ip,calculate"
    "mask"="subnet,cidr,netmask,prefix,255"
    "vlsm"="variable,length,subnet,mask,subnetting"
    "ip"="address,subnet,cidr,host,network,dhcp"
    "ssh"="secure,remote,login,telnet,crypto,rsa"
    "dhcp"="ip,address,lease,pool,network"
    "dns"="nameserver,resolve,lookup,domain"
    "ospf"="routing,router,rip,protocol,area"
    "nat"="translation,inside,outside,overload"
    "acl"="access,list,permit,deny,filter"
    "ou"="organisational,organizational,unit,container,aduc"
    "organisational"="ou,organizational,unit,container,aduc"
    "organizational"="ou,organisational,unit,container,aduc"
    "delegate"="permission,rights,control,assign"
    "sysprep"="clone,linked,generalize,oobe,vm"
    "linux"="unix,bash,shell,dnf,rpm,sudo,rocky"
    "sudo"="root,admin,privilege,superuser,wheel"
    "windows"="server,win,microsoft,ad,domain"
    "cisco"="router,switch,commands,cheat,sheet,networking"
    "promote"="dc,controller,domain,adds,forest"
    "private"="rfc,internal,range,1918,local"
    "binary"="decimal,convert,bits,octet"
    "broadcast"="address,subnet,network,last"
}

function Get-Variants([string]$t) {
    $list = @($t)
    if ($SynMap.ContainsKey($t)) { $list += $SynMap[$t] -split "," }
    return $list
}

# ── Tokenise query ────────────────────────────────────────────────────────────
$kb     = Import-Csv $CsvPath
$filler = "how","to","the","a","an","in","on","at","of","for","and","or",
          "is","are","into","onto","by","with","do","can","i","my","its","please"
$terms  = ($Query.ToLower() -split "\s+") |
          Where-Object { $_.Length -ge 2 -and $_ -notin $filler }
if ($terms.Count -eq 0) { $terms = $Query.ToLower() -split "\s+" }

# ── Two-tier matching ─────────────────────────────────────────────────────────
#
# directBlob = section + subsection + content  (the real text)
# tagBlob    = tags only                        (pre-expanded synonyms from Python)
#
# For each search term:
#   - "direct hit"  = term appears literally in directBlob
#   - "tag hit"     = term (or a synonym) appears in tagBlob
#
# A row is included when:
#   1. Every term gets at least a tag hit (nothing is completely unmatched)
#   2. At least ceil(terms/2) terms are direct hits
#      → 1 term:  1 direct needed
#      → 2 terms: 1 direct needed
#      → 3 terms: 2 direct needed
#      → 4 terms: 2 direct needed
#
# This means synonyms help recall without letting tag-only matches flood results.

$results = $kb | Where-Object {
    $direct = "$($_.section) $($_.subsection) $($_.content)".ToLower()
    $tags   = $_.tags.ToLower()

    $directHits = 0
    $allMatch   = $true

    foreach ($t in $terms) {
        if ($direct -like "*$t*") {
            $directHits++
        } else {
            # Check synonyms against both direct text and tags
            $synHit = $false
            foreach ($v in (Get-Variants $t)) {
                if ($direct -like "*$v*" -or $tags -like "*$v*") { $synHit = $true; break }
            }
            if (-not $synHit) { $allMatch = $false; break }
        }
    }

    if (-not $allMatch) { return $false }

    $needed = [math]::Ceiling($terms.Count / 2)
    if ($directHits -lt $needed) { return $false }

    if ($Section     -and $_.section -notlike "*$Section*") { return $false }
    if ($CommandOnly -and $_.type -ne "command") { return $false }
    if ($StepsOnly   -and $_.type -ne "steps")   { return $false }
    return $true
}

# ── Score ─────────────────────────────────────────────────────────────────────
$scored = $results | ForEach-Object {
    $s = 0
    foreach ($t in $terms) {
        if ($_.subsection -like "*$t*") { $s += 8 }
        if ($_.section    -like "*$t*") { $s += 4 }
        if ($_.content    -like "*$t*") { $s += 2 }
        if ($_.tags       -like "*$t*") { $s += 1 }
    }
    # Bonus when all terms appear together in the content
    $allInContent = ($terms | Where-Object { $_.content -notlike "*$_*" }).Count -eq 0
    if ($allInContent -and $terms.Count -gt 1) { $s += 5 }

    if ($_.type -eq "steps")   { $s += 2 }
    if ($_.type -eq "command") { $s += 1 }
    [PSCustomObject]@{ Row = $_; Score = $s }
} | Sort-Object Score -Descending

$total = ($scored | Measure-Object).Count
$shown = $scored | Select-Object -First $MaxResults

# ── Display ───────────────────────────────────────────────────────────────────
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host ""
if ($total -eq 0) {
    Write-Host "  No results for '$Query'" -ForegroundColor Yellow
    Write-Host "  Tips:" -ForegroundColor DarkGray
    Write-Host "   - Try fewer or different keywords, e.g. 'linux user' or 'create user'" -ForegroundColor DarkGray
    Write-Host "   - Use Browse by Topic (option 2) to explore categories" -ForegroundColor DarkGray
    Write-Host ""; exit 0
}

Write-Host "  " -NoNewline
Write-Host $total -NoNewline -ForegroundColor Cyan
Write-Host " result(s) for '$Query'" -ForegroundColor DarkGray
if ($total -gt $MaxResults) {
    Write-Host "  Showing top $MaxResults — use -MaxResults $total to see all" -ForegroundColor DarkGray
}

$i = 1
foreach ($item in $shown) {
    $row = $item.Row
    Write-Host ""
    Write-Host "  " -NoNewline
    Write-Host "─── [$i/$total] " -NoNewline -ForegroundColor DarkGray
    $tc = switch ($row.type) { "steps" {"Magenta"} "command" {"Green"} default {"Cyan"} }
    Write-Host "[$($row.type.ToUpper())]" -NoNewline -ForegroundColor $tc
    Write-Host " ─────────────────────────────────────" -ForegroundColor DarkGray
    $crumb = $row.section
    if ($row.subsection) { $crumb += "  >  $($row.subsection)" }
    Write-Host "  $crumb" -ForegroundColor White
    Write-Host "  Source: $($row.source)" -ForegroundColor DarkGray
    Write-Host ""
    foreach ($cl in ($row.content -split "`n")) {
        $cs = $cl.Trim()
        if (-not $cs) { continue }
        if ($cs -match "^(\d+)\.\s+(.+)$") {
            Write-Host "    " -NoNewline
            Write-Host "$($Matches[1])." -NoNewline -ForegroundColor Yellow
            Write-Host " $($Matches[2])" -ForegroundColor White
        } elseif ($cs -match "^([^#\n]+?)\s{2,}#\s+(.+)$") {
            Write-Host "    " -NoNewline
            Write-Host $Matches[1].TrimEnd() -NoNewline -ForegroundColor Green
            Write-Host "  # $($Matches[2])" -ForegroundColor DarkGray
        } elseif ($cs -match "^NOTE:") {
            Write-Host "    $cs" -ForegroundColor DarkYellow
        } elseif ($cs -match "^[-•*]\s+") {
            Write-Host "    $cs" -ForegroundColor Gray
        } elseif ($row.type -eq "command" -and $cs -notmatch "^[A-Z][a-z]") {
            Write-Host "    $cs" -ForegroundColor Green
        } else {
            Write-Host "    $cs" -ForegroundColor Gray
        }
    }
    $i++
}
Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""