# search_kb.ps1  –  v2
param(
    [Parameter(Position=0, Mandatory=$true)] [string]$Query,
    [string]$Section     = "",
    [switch]$CommandOnly,
    [switch]$StepsOnly,
    [int]   $MaxResults  = 15,
    [string]$CsvPath     = "",
    [switch]$NoGroup,
    [switch]$Fuzzy
)

if (-not $CsvPath) { $CsvPath = Join-Path $PSScriptRoot "knowledge_base.csv" }
if (-not (Test-Path $CsvPath)) { $CsvPath = "knowledge_base.csv" }
if (-not (Test-Path $CsvPath)) {
    Write-Host "`n  [ERROR] knowledge_base.csv not found." -ForegroundColor Red; exit 1
}

# ── Synonym map ───────────────────────────────────────────────────────────────
$SynMap = @{
    "add"="create,new,install,useradd,adduser,join,setup"
    "create"="add,new,make,setup,useradd,adduser,install,build"
    "remove"="delete,del,uninstall,userdel,erase"
    "delete"="remove,del,uninstall,userdel,erase"
    "install"="add,setup,deploy,enable,dnf,apt,configure"
    "setup"="configure,install,create,build,deploy,initialize"
    "join"="connect,add,domain,member,client,computer,desktop,pc"
    "desktop"="pc,computer,client,workstation,machine,join,windows,domain"
    "pc"="desktop,computer,client,workstation,machine"
    "computer"="pc,desktop,client,workstation,join,domain"
    "client"="pc,desktop,computer,workstation,join,domain,windows"
    "domain"="ad,active,directory,forest,dc,join,client,computer,adds,school"
    "active"="ad,directory,domain,adds,windows"
    "directory"="ad,active,domain,adds,aduc,adac"
    "active directory"="ad,adds,domain,dc,domain controller,aduc,adac,forest,school"
    "domain controller"="dc,promote,adds,forest,active directory,install,setup,create"
    "dc"="domain controller,promote,adds,forest,active directory"
    "user"="users,account,useradd,adduser,userdel,usermod,new-aduser"
    "group"="groups,groupadd,groupmod,groupdel,member,membership"
    "password"="passwd,pwd,pass,secret,chage,credentials"
    "show"="display,list,view,check,get,verify,print"
    "lock"="disable,block,usermod,deactivate"
    "unlock"="enable,unblock,usermod,activate"
    "interface"="int,port,fa,gi,eth,fastethernet,gigabit,nic"
    "vlan"="virtual,network,lan,trunk,access,switchport"
    "trunk"="uplink,inter,vlan,allowed,switchport"
    "router"="routing,route,ospf,rip,gateway,default"
    "routing"="route,ospf,rip,router,static,dynamic"
    "subnet"="subnetting,cidr,mask,prefix,network,ip,vlsm"
    "subnetting"="subnet,cidr,mask,vlsm,prefix,ip,calculate"
    "mask"="subnet,cidr,netmask,prefix,255,slash"
    "vlsm"="variable,length,subnet,mask,subnetting,efficient"
    "ip"="address,subnet,cidr,host,network,dhcp,ipv4"
    "ssh"="secure,remote,login,telnet,crypto,rsa,transport"
    "dhcp"="ip,address,lease,pool,network,dns"
    "dns"="nameserver,resolve,lookup,domain,bind,named"
    "ospf"="routing,router,rip,protocol,area,dynamic,passive"
    "rip"="routing,router,ospf,protocol,dynamic,distance,vector"
    "nat"="translation,inside,outside,overload,masquerade,pat"
    "acl"="access,list,permit,deny,filter,wildcard"
    "ou"="organisational,organizational,unit,container,aduc,adac"
    "organisational"="ou,organizational,unit,container,aduc,create"
    "organizational"="ou,organisational,unit,container,aduc,create"
    "delegate"="permission,rights,control,assign,wizard,ou"
    "sysprep"="clone,linked,generalize,oobe,vm,vmware,snapshot"
    "linux"="unix,bash,shell,dnf,rpm,sudo,rocky,redhat,rhel"
    "sudo"="root,admin,privilege,superuser,wheel,visudo,sudoers"
    "windows"="server,win,microsoft,ad,domain,active,directory"
    "cisco"="router,switch,commands,networking,ios"
    "promote"="dc,controller,domain,adds,forest,active directory"
    "private"="rfc,internal,range,1918,local"
    "binary"="decimal,convert,bits,octet,hex"
    "broadcast"="address,subnet,network,last,host"
    "pki"="ca,certificate,authority,adcs,tls,ssl,enrollment,template"
    "ca"="certificate,authority,pki,adcs,tls,ssl,root,enterprise"
    "certificate"="ca,pki,tls,ssl,adcs,crt,key,csr,enrollment,openssl"
    "tls"="ssl,certificate,ca,pki,encrypt,secure,starttls,https"
    "ssl"="tls,certificate,ca,pki,encrypt,secure,openssl"
    "vpn"="tunnel,remote,access,pptp,sstp,l2tp,ikev2,openvpn,wireguard,rras"
    "pptp"="vpn,rras,windows,tunnel,mschapv2,1723"
    "sstp"="vpn,ssl,tls,certificate,rras,windows,443"
    "openvpn"="vpn,linux,ssl,tls,easy-rsa,pki,certificate,1194,rocky"
    "wireguard"="vpn,linux,modern,udp,51820,peer,key"
    "rras"="routing,remote,access,windows,vpn,nat,router,server"
    "mail"="smtp,imap,pop3,postfix,dovecot,email,mta,mua"
    "postfix"="mail,smtp,mta,email,linux,main.cf,relay,sasl"
    "dovecot"="mail,imap,pop3,linux,maildir,ssl,authentication"
    "smtp"="mail,postfix,email,25,relay,send,mta,starttls"
    "imap"="mail,dovecot,email,143,receive,inbox,imaps"
    "lvm"="logical,volume,pv,vg,lv,extend,resize,disk,storage,snapshot"
    "raid"="mdadm,mirror,stripe,array,disk,redundancy,storage"
    "firewall"="firewall-cmd,iptables,port,allow,block,rule,zone"
    "selinux"="restorecon,semanage,chcon,context,label,enforcing"
    "gpo"="group,policy,windows,aduc,ou,baseline,security"
    "forest"="domain,active,directory,adds,dc,domain controller,promote"
}

function Get-Variants([string]$t) {
    $list = @($t)
    if ($SynMap.ContainsKey($t)) { $list += $SynMap[$t] -split "," }
    return $list
}

# ── Fuzzy match helper (Levenshtein distance) ─────────────────────────────────
function Get-LevenshteinDistance([string]$a, [string]$b) {
    $la = $a.Length; $lb = $b.Length
    if ($la -eq 0) { return $lb }
    if ($lb -eq 0) { return $la }
    # Two-row rolling approach using ArrayList — no 2D array indexing issues
    $prev = [System.Collections.ArrayList]::new()
    $curr = [System.Collections.ArrayList]::new()
    for ($j = 0; $j -le $lb; $j++) { [void]$prev.Add($j); [void]$curr.Add(0) }
    for ($i = 1; $i -le $la; $i++) {
        $curr[0] = $i
        for ($j = 1; $j -le $lb; $j++) {
            $cost = if ($a[$i-1] -eq $b[$j-1]) { 0 } else { 1 }
            $del  = $prev[$j]   + 1
            $ins  = $curr[$j-1] + 1
            $sub  = $prev[$j-1] + $cost
            $curr[$j] = [math]::Min([math]::Min($del, $ins), $sub)
        }
        for ($j = 0; $j -le $lb; $j++) { $prev[$j] = $curr[$j] }
    }
    return $prev[$lb]
}

function Test-FuzzyMatch([string]$term, [string]$blob, [int]$maxDist=1) {
    # Split blob into words and check if any word is within $maxDist edits of $term
    foreach ($word in ($blob -split "[\s,]+")) {
        if ($word.Length -ge 3 -and [math]::Abs($word.Length - $term.Length) -le $maxDist) {
            if ((Get-LevenshteinDistance $term $word) -le $maxDist) { return $true }
        }
    }
    return $false
}

# ── Tokenise query ────────────────────────────────────────────────────────────
$kb = Import-Csv $CsvPath

# Filler words stripped before matching
$filler = "how","to","the","a","an","in","on","at","of","for","and","or",
          "is","are","into","onto","by","with","do","can","i","my","its",
          "please","what","where","show","me","give","find","get","list",
          "steps","step","way","ways","using","use"

$queryLower = $Query.ToLower().Trim()

# ── Intent rewriting — convert natural language to canonical search terms ──────
# Must run FIRST, before phrase detection and term splitting.
# ── Pre-processing: extract CIDR notation before filler stripping eats it ──────
# Turn "/26" or "slash 26" into the word "slash26" so it survives tokenisation
$cidrMatch = [regex]::Match($queryLower, '(?<![0-9])/([0-9]{1,2})(?![0-9])')
$slashWord  = ""
if ($cidrMatch.Success) {
    $slashNum  = $cidrMatch.Groups[1].Value
    $slashWord = "/$slashNum"          # keep as-is, e.g. "/26"
    $queryLower = $queryLower -replace [regex]::Escape($slashWord), "cidr$slashNum"
}

$intentMap = @{
    # ── Subnetting natural-language questions ─────────────────────────────
    "how many hosts.*/(2[0-9]|3[0-2])"  = "hosts subnet cidr"
    "how many hosts"                     = "hosts subnet"
    "hosts per subnet"                   = "hosts subnet"
    "number of hosts"                    = "hosts subnet"
    "usable hosts"                       = "hosts subnet usable"
    "subnet size"                        = "subnet block size"
    "block size"                         = "subnet block size"
    "how many subnets"                   = "subnets borrowed bits"
    "borrow.*bits"                       = "borrowed bits subnets"
    "calculate subnet"                   = "subnet calculate"
    "what is.*subnet"                    = "subnet"
    # ── Domain join ───────────────────────────────────────────────────────
    "add.*desktop.*domain"               = "join domain"
    "add.*computer.*domain"              = "join domain"
    "add.*pc.*domain"                    = "join domain"
    "add.*client.*domain"               = "join domain"
    "add.*server.*domain"               = "join domain"
    "add.*workstation.*domain"           = "join domain"
    "add.*machine.*domain"              = "join domain"
    "add.*to.*domain"                    = "join domain"
    "connect.*to.*domain"        = "join domain"
    "put.*on.*domain"            = "join domain"
    "domain.*join"               = "join domain"
    "join.*the.*domain"          = "join domain"
    "join.*domain"               = "join domain"
    # "create/add domain controller" → promote dc
    "add.*domain.*controller"    = "promote domain controller"
    "create.*domain.*controller" = "promote domain controller"
    "make.*domain.*controller"   = "promote domain controller"
    "new.*domain.*controller"    = "promote domain controller"
}

foreach ($pattern in $intentMap.Keys) {
    if ($queryLower -match $pattern) {
        $queryLower = $intentMap[$pattern]
        break
    }
}

# Re-inject CIDR term (e.g. "cidr26" → kept as extra term alongside rewritten query)
if ($slashWord -ne "") {
    $slashNum2 = $slashWord -replace "/",""
    # Only keep CIDR term if query didn't already get a full rewrite
    if ($queryLower -notlike "*cidr*" -and $queryLower -notlike "*subnet*") {
        $queryLower = "$queryLower /$slashNum2"
    }
}

# ── Phrase detection ──────────────────────────────────────────────────────────
$phrases = [System.Collections.Generic.List[string]]::new()
$remainingQuery = $queryLower

$knownPhrases = @(
    "active directory","domain controller","group policy","certificate authority",
    "remote access","nat overload","access list","easy-rsa",
    "ip helper","default route","passive interface","static route","floating static",
    "port forwarding","server isolation","domain isolation","logical volume",
    "physical volume","volume group","variable length",
    "join domain","add computer","add-computer","join workgroup","leave domain",
    "promote dc","promote server"
)

foreach ($phrase in $knownPhrases) {
    if ($remainingQuery -like "*$phrase*") {
        $phrases.Add($phrase)
        $remainingQuery = $remainingQuery -replace [regex]::Escape($phrase), " "
    }
}

# Individual terms after phrase extraction
# Allow CIDR notation (/26 etc), pure numbers (26, 255), and normal words
$terms = ($remainingQuery -split "\s+") | Where-Object {
    $w = $_
    ($w -match '^/[0-9]{1,2}$') -or          # /26 /24 etc
    ($w -match '^[0-9]+$' -and $w.Length -ge 2) -or  # plain numbers
    ($w.Length -ge 2 -and $w -notin $filler)
}

# Combine: phrases count as single high-value terms
$allTerms  = @($phrases) + @($terms)
if ($allTerms.Count -eq 0) { $allTerms = $queryLower -split "\s+" }

# ── Matching function ─────────────────────────────────────────────────────────
function Test-RowMatch($row, $terms, $phrases, [bool]$useFuzzy) {
    $direct = "$($row.section) $($row.subsection) $($row.content)".ToLower()
    $tags   = $row.tags.ToLower()
    $both   = "$direct $tags"

    $directHits = 0
    $allMatch   = $true

    foreach ($t in $terms) {
        $isPhrase = $phrases -contains $t
        if ($direct -like "*$t*") {
            $directHits++
        } elseif ($tags -like "*$t*") {
            $directHits += 0.5
        } elseif ($isPhrase) {
            # Phrase not found verbatim — check if ALL individual words are present
            # e.g. "join domain" not in "JOIN A WINDOWS CLIENT TO THE DOMAIN"
            # but "join" and "domain" are both there separately → counts as a hit
            $phraseWords = $t -split "\s+"
            $allWordsPresent = $true
            foreach ($pw in $phraseWords) {
                if ($direct -notlike "*$pw*" -and $tags -notlike "*$pw*") {
                    $allWordsPresent = $false; break
                }
            }
            if ($allWordsPresent) { $directHits++ }
            else {
                # Try synonyms as last resort
                $synHit = $false
                foreach ($v in (Get-Variants $t)) {
                    if ($both -like "*$v*") { $synHit = $true; break }
                }
                if (-not $synHit) { $allMatch = $false; break }
            }
        } else {
            # Try synonyms
            $synHit = $false
            foreach ($v in (Get-Variants $t)) {
                if ($both -like "*$v*") { $synHit = $true; break }
            }
            if (-not $synHit -and $useFuzzy -and $t.Length -ge 4) {
                $synHit = Test-FuzzyMatch $t $both 1
            }
            if (-not $synHit) { $allMatch = $false; break }
        }
    }

    if (-not $allMatch) { return $false }

    $needed = [math]::Ceiling($terms.Count / 2)
    if ($terms.Count -le 1) { $needed = 1 }
    if ([math]::Floor($directHits) -lt $needed) { return $false }
    if ($Section     -and $row.section -notlike "*$Section*")   { return $false }
    if ($CommandOnly -and $row.type -ne "command")              { return $false }
    if ($StepsOnly   -and $row.type -ne "steps")                { return $false }
    return $true
}

# ── First pass: exact/synonym matching ───────────────────────────────────────
$results = $kb | Where-Object { Test-RowMatch $_ $allTerms $phrases $false }

# ── Fuzzy fallback: if no results, retry with fuzzy matching ─────────────────
$usedFuzzy    = $false
$fuzzyCorrections = @{}   # term → what it actually matched

if (($results | Measure-Object).Count -eq 0) {
    $results   = $kb | Where-Object { Test-RowMatch $_ $allTerms $phrases $true }
    $usedFuzzy = ($results | Measure-Object).Count -gt 0

    # Find what each term fuzzy-matched to (for "Did you mean?" display)
    if ($usedFuzzy) {
        $sampleBlob = ($results | Select-Object -First 1 | ForEach-Object {
            "$($_.section) $($_.subsection) $($_.tags) $($_.content)"
        }).ToLower()
        foreach ($t in $allTerms) {
            $direct = $sampleBlob -like "*$t*"
            if (-not $direct -and $t.Length -ge 4) {
                foreach ($word in ($sampleBlob -split "[\s,]+")) {
                    if ($word.Length -ge 3 -and [math]::Abs($word.Length - $t.Length) -le 1) {
                        if ((Get-LevenshteinDistance $t $word) -le 1) {
                            $fuzzyCorrections[$t] = $word; break
                        }
                    }
                }
            }
        }
    }
}

# ── Scoring ───────────────────────────────────────────────────────────────────
#
# Points per match location:
#   subsection title  = 10  (most specific — user probably wants exactly this)
#   section title     =  6
#   phrase match      = +5 bonus on top of location score
#   content           =  3
#   tags              =  1
#   all terms together in content = +6 bonus
#   type bonus: steps = +3, command = +1
#
# Weight multiplier (from main.py v10 TF-IDF baked into CSV):
#   final_score = raw_score * (weight * 2.0 + 0.5)
#   entries about rare/specific topics beat generic ones
#   gracefully ignored if CSV has no weight column (older CSV)
#
# ── Scoring ───────────────────────────────────────────────────────────────────
#
# Points per DIRECT match location (synonym-only matches score 0):
#   subsection title  = 10  (most specific)
#   section title     =  6
#   phrase match      = +5 bonus on top of location score
#   content (direct)  =  3
#   tags (direct)     =  1
#   synonym-only hit  =  0  (still passes filter, but doesn't push result up)
#
# Bonus scoring:
#   all terms directly in content = +6
#   type: steps=+3, command=+1
#
# Weight multiplier from main.py TF-IDF:
#   final_score = raw_score * (weight * 2.0 + 0.5)
#
$scored = $results | ForEach-Object {
    $row  = $_
    $s    = 0
    $direct  = "$($row.section) $($row.subsection) $($row.content)".ToLower()
    $tagsTxt = $row.tags.ToLower()

    foreach ($t in $allTerms) {
        $isPhrase    = $phrases -contains $t
        $phraseBonus = if ($isPhrase) { 5 } else { 0 }

        # Only score DIRECT hits — synonym hits pass the filter but add no score
        if     ($row.subsection -like "*$t*") { $s += 10 + $phraseBonus }
        elseif ($row.section    -like "*$t*") { $s +=  6 + $phraseBonus }
        elseif ($row.content    -like "*$t*") { $s +=  3 + $phraseBonus }
        elseif ($tagsTxt        -like "*$t*") { $s +=  1 }
        elseif ($isPhrase) {
            # Phrase not found as exact string — try scoring each word individually
            # e.g. "join domain" misses "JOIN A WINDOWS CLIENT TO THE DOMAIN"
            # but "join" and "domain" are both there separately → partial phrase credit
            $phraseWords   = $t -split "\s+"
            $wordsInSub    = ($phraseWords | Where-Object { $row.subsection -like "*$_*" }).Count
            $wordsInSec    = ($phraseWords | Where-Object { $row.section    -like "*$_*" }).Count
            $wordsInCont   = ($phraseWords | Where-Object { $row.content    -like "*$_*" }).Count
            $wordsInTags   = ($phraseWords | Where-Object { $tagsTxt        -like "*$_*" }).Count
            $ratio         = [math]::Round(($wordsInSub + $wordsInSec + $wordsInCont + $wordsInTags) / $phraseWords.Count, 1)
            if    ($wordsInSub  -eq $phraseWords.Count) { $s += 8 }   # all words in subsection
            elseif($wordsInSec  -eq $phraseWords.Count) { $s += 5 }   # all words in section
            elseif($wordsInCont -eq $phraseWords.Count) { $s += 3 }   # all words in content
            elseif($ratio -ge 0.5)                      { $s += 1 }   # at least half the words
        }
        # synonym-only: 0 points — entry visible but ranked lower
    }

    # Bonus: all terms directly in content together (strong signal)
    $allInContent = $true
    foreach ($t in $allTerms) {
        if ($row.content -notlike "*$t*") { $allInContent = $false; break }
    }
    if ($allInContent -and $allTerms.Count -gt 1) { $s += 6 }

    # Bonus: query terms appear in subsection as a phrase (very strong signal)
    $subLower = $row.subsection.ToLower()
    $allInSub = $allTerms | Where-Object { $subLower -like "*$_*" }
    if (($allInSub | Measure-Object).Count -eq $allTerms.Count -and $allTerms.Count -gt 1) {
        $s += 8
    }

    # Type bonus
    if ($row.type -eq "steps")   { $s += 3 }
    if ($row.type -eq "command") { $s += 1 }

    # TF-IDF quality weight baked in by main.py v10
    $w = 1.0
    if ($row.PSObject.Properties.Name -contains "weight" -and $row.weight -ne "") {
        try { $w = [double]$row.weight * 2.0 + 0.5 } catch {}
    }

    [PSCustomObject]@{ Row = $row; Score = [math]::Round($s * $w, 2) }
} | Sort-Object Score -Descending

$total = ($scored | Measure-Object).Count
$shown = $scored | Select-Object -First $MaxResults

# ── Grouping by source ────────────────────────────────────────────────────────
# When multiple results come from the same source, group them visually
# unless -NoGroup is passed.
function Get-SourceGroups($items) {
    $groups = [System.Collections.Generic.List[object]]::new()
    $seen   = @{}
    foreach ($item in $items) {
        $src = $item.Row.source
        if (-not $seen.ContainsKey($src)) {
            $seen[$src] = $groups.Count
            $groups.Add([PSCustomObject]@{ Source = $src; Items = [System.Collections.Generic.List[object]]::new() })
        }
        $groups[$seen[$src]].Items.Add($item)
    }
    return $groups
}

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

# Header
Write-Host "  " -NoNewline
Write-Host $total -NoNewline -ForegroundColor Cyan
Write-Host " result(s) for '" -NoNewline -ForegroundColor DarkGray
Write-Host $Query -NoNewline -ForegroundColor White
Write-Host "'" -ForegroundColor DarkGray

if ($usedFuzzy) {
    if ($fuzzyCorrections.Count -gt 0) {
        $corrections = $fuzzyCorrections.GetEnumerator() | ForEach-Object { "'$($_.Key)' → '$($_.Value)'" }
        Write-Host "  Did you mean: " -NoNewline -ForegroundColor DarkYellow
        Write-Host ($corrections -join "  ") -ForegroundColor Yellow
    } else {
        Write-Host "  (no exact matches — showing fuzzy results)" -ForegroundColor DarkYellow
    }
}
if ($phrases.Count -gt 0) {
    Write-Host "  Phrases detected: " -NoNewline -ForegroundColor DarkGray
    Write-Host ($phrases -join ", ") -ForegroundColor Cyan
}
if ($total -gt $MaxResults) {
    Write-Host "  Showing top $MaxResults — use -MaxResults $total to see all" -ForegroundColor DarkGray
}

# ── Highlighted text helper ───────────────────────────────────────────────────
# Splits a line on matched search terms and prints matches in bright yellow.
function Write-Highlighted([string]$text, [string]$baseColor, [string]$indent = "    ") {
    $escaped = ($allTerms | Sort-Object Length -Descending | ForEach-Object { [regex]::Escape($_) })
    $pattern = $escaped -join "|"
    if (-not $pattern) { Write-Host "$indent$text" -ForegroundColor $baseColor; return }
    try {
        $parts = [regex]::Split($text, "($pattern)", "IgnoreCase")
    } catch {
        Write-Host "$indent$text" -ForegroundColor $baseColor; return
    }
    Write-Host $indent -NoNewline
    foreach ($part in $parts) {
        if ($part -and $part -match "^(?i:$pattern)$") {
            Write-Host $part -NoNewline -ForegroundColor Yellow
        } elseif ($part) {
            Write-Host $part -NoNewline -ForegroundColor $baseColor
        }
    }
    Write-Host ""
}

# ── Render entries (grouped or flat) ─────────────────────────────────────────
function Write-Entry($item, $index, $total) {
    $row = $item.Row
    Write-Host ""
    Write-Host "  " -NoNewline
    Write-Host "─── [$index/$total] " -NoNewline -ForegroundColor DarkGray
    $tc = switch ($row.type) { "steps" {"Magenta"} "command" {"Green"} default {"Cyan"} }
    Write-Host "[$($row.type.ToUpper())]" -NoNewline -ForegroundColor $tc
    Write-Host " ─────────────────────────────────────" -ForegroundColor DarkGray

    $crumb = $row.section
    if ($row.subsection) { $crumb += "  >  $($row.subsection)" }
    Write-Host "  $crumb" -ForegroundColor White
    Write-Host ""

    foreach ($cl in ($row.content -split "`n")) {
        $cs = $cl.Trim()
        if (-not $cs) { continue }
        if ($cs -match "^(\d+)\.\s+(.+)$") {
            Write-Host "    " -NoNewline
            Write-Host "$($Matches[1])." -NoNewline -ForegroundColor Yellow
            Write-Highlighted $Matches[2] "White" ""
        } elseif ($cs -match "^([^#\n]+?)\s{2,}#\s+(.+)$") {
            Write-Highlighted $Matches[1].TrimEnd() "Green" "    "
        } elseif ($cs -match "^NOTE:|^TIP:|^WARNING:") {
            Write-Highlighted $cs "DarkYellow" "    "
        } elseif ($cs -match "^[-•*]\s+") {
            Write-Highlighted $cs "Gray" "    "
        } elseif ($row.type -eq "command" -and $cs -notmatch "^[A-Z][a-z]") {
            Write-Highlighted $cs "Green" "    "
        } else {
            Write-Highlighted $cs "Gray" "    "
        }
    }
}

$i = 1
if ($NoGroup) {
    # Flat list — original behaviour
    foreach ($item in $shown) {
        Write-Entry $item $i $total
        $i++
    }
} else {
    # Grouped by source
    $groups = Get-SourceGroups $shown
    foreach ($group in $groups) {
        if ($group.Items.Count -gt 1) {
            Write-Host ""
            Write-Host "  ══ " -NoNewline -ForegroundColor DarkGray
            Write-Host $group.Source -NoNewline -ForegroundColor Yellow
            Write-Host " ($($group.Items.Count) results) " -NoNewline -ForegroundColor DarkGray
            Write-Host "══" -ForegroundColor DarkGray
        }
        foreach ($item in $group.Items) {
            Write-Entry $item $i $total
            $i++
        }
    }
}

Write-Host ""
Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""