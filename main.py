"""
txt_to_kb.py  –  v7
====================
Run ONCE at home to generate knowledge_base.csv from your .txt files.

Install dependencies first:
    pip install nltk rapidfuzz

Then on first run, nltk will auto-download its data files (~3MB, one time only).

After generating, copy these 3 files to any PC — no Python needed there:
    knowledge_base.csv
    search_kb.ps1
    kb.bat

Usage:
    python txt_to_kb.py
    python txt_to_kb.py --folder C:\\notes\\txt --out C:\\kb\\knowledge_base.csv
"""

import re, csv
from pathlib import Path

# ── Optional NLP imports ───────────────────────────────────────────────────
try:
    import nltk
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    from nltk.corpus import stopwords as nltk_stopwords

    for _pkg in ("wordnet", "omw-1.4", "stopwords"):
        try:
            nltk.data.find(f"corpora/{_pkg}")
        except LookupError:
            print(f"  [nltk] Downloading '{_pkg}'...")
            nltk.download(_pkg, quiet=True)

    _stemmer    = PorterStemmer()
    _lemmatizer = WordNetLemmatizer()
    _nltk_stop  = set(nltk_stopwords.words("english"))
    NLP_AVAILABLE = True
    print("  [nltk] NLP active — richer tags enabled")
except ImportError:
    NLP_AVAILABLE = False
    _stemmer = _lemmatizer = _nltk_stop = None
    print("  [warn] nltk not found. Install with: pip install nltk rapidfuzz")
    print("         Continuing with built-in tags (still works fine).")

# ══════════════════════════════════════════════════════════════════════════════
#  CURATED KEYWORD TABLES
# ══════════════════════════════════════════════════════════════════════════════

# All entries from a source file get these tags injected.
# Guarantees browse queries like "linux user" always hit user_cheat_sheet entries.
SOURCE_KEYWORDS: dict = {
    "user_cheat_sheet": [
        # Most-searched browse terms first (never get truncated)
        "linux","windows","user","group","sudo","package","organisational","ou",
        "desktop","pc","client","computer","join","domain","active","directory",
        "ad","adds","aduc","powershell","delegation","sysprep","config","management",
        # Linux detail
        "unix","shell","bash","rocky","redhat","rhel",
        "users","account","useradd","adduser","userdel","usermod",
        "groups","groupadd","groupmod","groupdel",
        "password","passwd","shadow","chage","lock","unlock","expire","aging",
        "sudoers","visudo","root","wheel","privilege","admin",
        "dnf","rpm","yum","install","remove","upgrade",
        "configuration","skel","profile","reference",
        # Windows / AD detail
        "server","microsoft","win",
        "forest","dc","controller","adac","gpo","policy",
        "organizational","unit","container",
        "promote","delegate","rights","permission","control",
        "clone","linked","generalize","oobe","vm","vmware",
        "module","rsat","import","csv","bulk","script",
        "dsadd","dsmod","dsquery","dsmove","csvde","ldifde","cli","command","line",
        "roaming","homefolder","share","path","sysvol",
        "workstation","machine","cheat","sheet",
    ],
    "cisco_cheat_sheet": [
        "cisco","router","switch","networking","commands",
        "interface","fastethernet","gigabit","fa","gi","port","nic",
        "vlan","trunk","access","switchport","allowed","lan",
        "routing","route","ospf","rip","static","default","gateway",
        "ssh","telnet","crypto","rsa","transport","remote","login",
        "acl","permit","deny","filter","wildcard",
        "nat","translation","inside","outside","overload",
        "dhcp","pool","dns","lease",
        "password","secret","console","vty","banner","motd","hostname",
        "enable","configure","privileged","exec","mode","global",
        "cheat","sheet","reference",
    ],
    "cisco_commands": [
        "cisco","router","switch","commands","reference","all",
        "interface","fastethernet","gigabit","vlan","trunk",
        "routing","ospf","rip","ssh","acl","nat","dhcp",
        "enable","configure","show","debug","ping","traceroute",
    ],
    "cisco_steps": [
        "cisco","switch","vlan","trunk","configure","steps","walkthrough",
        "password","banner","access","port","fastethernet","setup",
    ],
    "subnet_cheat_sheet": [
        "subnet","subnetting","cidr","mask","netmask","prefix","slash",
        "ip","ipv4","address","host","hosts","network","broadcast",
        "block","blocksize","increment","range","usable",
        "binary","decimal","octet","bits","convert","reference",
        "private","rfc","1918","internal","class","wildcard",
        "vlsm","variable","length","efficient","cheat","sheet",
    ],
    "ultimatesubnet_cheat_sheet": [
        "subnet","subnetting","cidr","mask","netmask","prefix","slash",
        "ip","ipv4","address","host","hosts","network","broadcast",
        "block","blocksize","formula","calculate","usable","range",
        "binary","decimal","octet","bits","convert",
        "vlsm","variable","length","efficient","assign","allocate",
        "private","rfc","1918","special","loopback","apipa",
        "split","divide","example","worked","cheat","sheet","ultimate",
    ],
}

# Extra keywords matched by section/subsection content
SECTION_KEYWORDS: dict = {
    "user & group":           ["linux","user","group","useradd","userdel","usermod","groupadd","groupdel","management","account"],
    "linux - user":           ["linux","user","useradd","userdel","usermod","adduser","account"],
    "linux - package":        ["linux","package","dnf","install","remove","upgrade","rpm"],
    "package management":     ["linux","package","dnf","rpm","install","remove","upgrade","group"],
    "sudo":                   ["linux","sudo","root","admin","privilege","wheel","visudo","sudoers"],
    "permissions":            ["linux","sudo","chmod","chown","permission","rights","privilege"],
    "config files":           ["linux","config","passwd","shadow","sudoers","skel","group","reference","paths"],
    "verification":           ["linux","verify","check","id","rpm","query","man"],
    "password":               ["linux","windows","password","passwd","chage","expire","lock","aging","policy"],
    "active directory setup": ["windows","active","directory","ad","adds","domain","install","setup","gui"],
    "domain controller":      ["windows","domain","controller","promote","dc","forest","adds","roles"],
    "promote":                ["windows","domain","controller","promote","dc","forest","adds"],
    "organisational":         ["windows","ou","organisational","organizational","unit","aduc","adac","container","create"],
    "organizational":         ["windows","ou","organisational","organizational","unit","aduc","adac","container","create"],
    "user management":        ["windows","user","aduc","adac","template","copy","profile","home","folder","create","disable"],
    "powershell":             ["windows","powershell","cmdlet","new-aduser","import-csv","module","script","bulk"],
    "command line ad":        ["windows","dsadd","dsmod","dsquery","dsmove","csvde","ldifde","cli","command","line"],
    "delegation":             ["windows","delegate","delegation","control","permission","rights","wizard","ou"],
    "sysprep":                ["windows","sysprep","clone","linked","generalize","oobe","vm","vmware","snapshot"],
    "quick reference":        ["paths","reference","etc","windows","linux","sysvol","roaming","homefolder","important"],
    "join":                   ["windows","join","domain","client","pc","desktop","computer","workstation","machine"],
    "windows client":         ["windows","join","domain","client","pc","desktop","computer","workstation","machine"],
    "vlan":                   ["cisco","vlan","trunk","access","switchport","allowed","port","mode"],
    "routing":                ["cisco","routing","route","ospf","rip","static","default","gateway","table"],
    "ssh":                    ["cisco","ssh","crypto","rsa","transport","vty","login","local","secure","remote"],
    "acl":                    ["cisco","acl","access","list","permit","deny","filter","wildcard","inbound","outbound"],
    "nat":                    ["cisco","nat","translation","inside","outside","overload","masquerade","pat"],
    "dhcp":                   ["cisco","dhcp","pool","network","router","dns","lease","default"],
    "the basics":             ["subnet","subnetting","basics","ipv4","network","host","mask","portion","split"],
    "slash notation":         ["subnet","cidr","slash","notation","prefix","bits","ones","zeros"],
    "special addresses":      ["subnet","special","network","broadcast","usable","first","last","formula"],
    "formula":                ["subnet","formula","block","size","calculate","usable","hosts","256"],
    "reference table":        ["subnet","reference","table","hosts","block","size","subnets","cidr"],
    "picking the right":      ["subnet","pick","choose","size","hosts","needed","fit","requirements"],
    "splitting":              ["subnet","split","divide","example","27","subnets","block","network"],
    "vlsm":                   ["subnet","vlsm","variable","length","efficient","assign","allocate","largest","first","steps"],
    "private ip":             ["subnet","private","ip","rfc","1918","range","internal","class","not","routable"],
    "special address":        ["subnet","special","loopback","apipa","broadcast","default","route","unspecified"],
    "binary":                 ["subnet","binary","decimal","convert","bits","octet","position","value","hex"],
    "quick cheat":            ["subnet","quick","card","reference","summary","formula","vlsm"],
}

SYNONYMS: dict = {
    "add":            ["create","new","useradd","adduser","install","join","make"],
    "create":         ["add","new","make","useradd","adduser","setup","configure"],
    "remove":         ["delete","del","userdel","uninstall","erase","drop"],
    "delete":         ["remove","del","userdel","erase","drop"],
    "install":        ["add","setup","deploy","enable","dnf","apt","rpm"],
    "configure":      ["config","setup","set","customise","customize"],
    "enable":         ["activate","allow","permit","start"],
    "disable":        ["lock","deactivate","prevent","block"],
    "lock":           ["disable","block","usermod","prevent","deactivate"],
    "unlock":         ["enable","unblock","activate","usermod"],
    "show":           ["display","list","view","check","get","verify","print"],
    "join":           ["connect","add","domain","member","client","desktop","pc","computer"],
    "promote":        ["dc","controller","domain","adds","forest","roles"],
    "user":           ["users","account","useradd","adduser","userdel","usermod","person","login"],
    "group":          ["groups","groupadd","groupmod","groupdel","member","membership"],
    "password":       ["passwd","chage","secret","credentials","pass","pwd"],
    "desktop":        ["pc","computer","client","workstation","machine","join","windows","domain"],
    "pc":             ["desktop","computer","client","workstation","machine"],
    "computer":       ["pc","desktop","client","workstation","machine","join","domain"],
    "client":         ["pc","desktop","computer","workstation","join","domain","windows"],
    "domain":         ["ad","active","directory","forest","dc","join","client","computer"],
    "active":         ["ad","directory","domain","adds","windows"],
    "directory":      ["ad","active","domain","adds","aduc","adac"],
    "ou":             ["organisational","organizational","unit","container","aduc","adac"],
    "organisational": ["ou","organizational","unit","container","aduc","create"],
    "organizational": ["ou","organisational","unit","container","aduc","create"],
    "dc":             ["domain","controller","promote","adds","forest"],
    "interface":      ["fastethernet","gigabit","fa","gi","eth","port","nic","int"],
    "vlan":           ["trunk","access","switchport","lan","virtual","network"],
    "trunk":          ["uplink","inter","vlan","allowed","switchport","mode"],
    "router":         ["routing","ospf","rip","route","gateway","default"],
    "routing":        ["route","ospf","rip","router","static","dynamic","table"],
    "subnet":         ["subnetting","cidr","mask","vlsm","prefix","ip","network"],
    "subnetting":     ["subnet","cidr","mask","vlsm","prefix","ip","calculate","network"],
    "mask":           ["subnet","cidr","netmask","prefix","255","slash"],
    "vlsm":           ["variable","length","subnet","mask","subnetting","efficient","assign"],
    "cidr":           ["slash","prefix","notation","mask","subnet","bits"],
    "ip":             ["address","subnet","cidr","host","network","dhcp","ipv4"],
    "ssh":            ["secure","remote","login","telnet","crypto","rsa","transport","vty"],
    "acl":            ["access","list","permit","deny","filter","wildcard"],
    "nat":            ["translation","inside","outside","overload","masquerade","pat"],
    "dhcp":           ["ip","address","lease","pool","network","dns","router"],
    "block":          ["size","increment","subnet","cidr","range","256"],
    "broadcast":      ["address","subnet","network","last","host","bits"],
    "private":        ["rfc","1918","internal","range","class","local"],
    "binary":         ["decimal","convert","bits","octet","position","hex","base"],
    "cisco":          ["router","switch","networking","commands","ios"],
    "linux":          ["unix","bash","shell","dnf","rpm","sudo","rocky","redhat","rhel"],
    "windows":        ["server","win","microsoft","ad","domain","active","directory"],
    "sudo":           ["root","admin","privilege","superuser","wheel","escalate","visudo"],
    "package":        ["dnf","apt","rpm","install","software","program","module"],
    "sysprep":        ["clone","linked","generalize","oobe","vm","vmware","snapshot","image"],
    "delegate":       ["permission","rights","control","assign","wizard","ou","grant"],
}

STOP_WORDS = {
    "the","and","for","with","that","this","from","into","are","all",
    "not","can","its","per","run","see","via","etc","will","only","also",
    "any","but","was","has","get","you","your","then","when","each","both",
    "been","have","they","their","over","more","these","those","such","just",
    "here","note","does","make","below","above","using","used","same","line",
    "mode","type","item","than","after","next","start","first","last","every",
    "need","give","well","back","between","which","where","about","like",
    "what","how","use","set","new","one","two","out","its",
}


def _stem(w):
    if NLP_AVAILABLE: return _stemmer.stem(w)
    for suf in ("ing","tion","ed","ment","ers","er"):
        if w.endswith(suf) and len(w) - len(suf) > 3: return w[:-len(suf)]
    if w.endswith("s") and len(w) > 4: return w[:-1]
    return w


def _lemma(w):
    return _lemmatizer.lemmatize(w) if NLP_AVAILABLE else w


def _is_stop(w):
    if w in STOP_WORDS: return True
    if NLP_AVAILABLE and w in _nltk_stop: return True
    return False


def make_tags(source, section, subsection, content):
    seen, tags = set(), []

    def add(*words):
        for w in words:
            w = str(w).strip().lower()
            if w and len(w) >= 2 and w not in seen:
                seen.add(w)
                tags.append(w)
                for syn in SYNONYMS.get(w, []):
                    syn = syn.strip()
                    if syn and syn not in seen:
                        seen.add(syn); tags.append(syn)

    # 1. Source-level keywords
    for kw in SOURCE_KEYWORDS.get(source, []):
        add(kw)

    # 2. Section/subsection topic keywords
    blob_sec = (section + " " + subsection).lower()
    for key, words in SECTION_KEYWORDS.items():
        if key in blob_sec:
            for w in words: add(w)

    # 3. Words extracted from all text fields
    all_text = f"{section} {subsection} {content}".lower()
    for w in re.findall(r"[a-z][a-z0-9\-]{1,}", all_text):
        if _is_stop(w): continue
        add(w, _stem(w), _lemma(w))
        # Split compound tokens: useradd→add, groupdel→del, fastethernet→ethernet
        for pfx in ("user","group","net","fast","get","ip","no","show"):
            if w.startswith(pfx) and len(w) > len(pfx) + 2:
                add(w[len(pfx):])

    return ",".join(tags[:150])


# ══════════════════════════════════════════════════════════════════════════════
#  PARSING
# ══════════════════════════════════════════════════════════════════════════════

EQ_DIVIDER    = re.compile(r"^={8,}\s*$")
DASH_DIVIDER  = re.compile(r"^-{8,}\s*$")
UNDER_DIVIDER = re.compile(r"^_{8,}\s*$")
ANY_DIVIDER   = re.compile(r"^[=\-_]{8,}\s*$")
SHORT_DASH    = re.compile(r"^\s*-{3,}\s*$")
BLANK         = re.compile(r"^\s*$")
NUMBERED_HEAD = re.compile(r"^(\d+)\.\s+([A-Z].{3,60})$")
ALL_CAPS_RE   = re.compile(r"^[A-Z][A-Z0-9 :/#\-&().,]{3,}$")
SUBHEAD_RE    = re.compile(r"^[A-Z][A-Za-z0-9 /&()\-]{2,50}$")
CMD_RE        = re.compile(r"^[\w./\\$%{}<>()\[\]!#@\-]")
GUI_STEP_RE   = re.compile(r"^\s*\d+\.\s+\S")


def detect_type(lines):
    if sum(1 for l in lines if GUI_STEP_RE.match(l)) >= 2: return "steps"
    for l in lines:
        s = l.strip()
        if s and not s.startswith("#") and CMD_RE.match(s): return "command"
    return "prose"


def pack(lines):
    return "\n".join(l.strip() for l in lines if l.strip())


def make_row(source, section, subsection, lines):
    cl = [l for l in lines if l.strip()]
    if not cl: return None
    content = pack(cl)
    if len(content) < 4: return None
    return {
        "source": source, "section": section, "subsection": subsection,
        "type": detect_type(cl), "content": content,
        "tags": make_tags(source, section, subsection, content),
    }


def detect_format(lines):
    for l in lines[:10]:
        if UNDER_DIVIDER.match(l.strip()): return "underline"
    for l in lines[:15]:
        s = l.strip()
        if EQ_DIVIDER.match(s) or DASH_DIVIDER.match(s): return "dash_sections"
    return "flat"


def parse_dash_sections(lines, source):
    rows = []; section = source.replace("_"," ").upper(); subsection = ""; block = []
    def flush(b,sec,sub):
        r = make_row(source,sec,sub,b)
        if r: rows.append(r)
    i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip(); i += 1
        if ANY_DIVIDER.match(s):
            j = i
            while j < len(lines) and BLANK.match(lines[j].strip()): j += 1
            if j < len(lines):
                c = lines[j].strip()
                if NUMBERED_HEAD.match(c) or ALL_CAPS_RE.match(c):
                    flush(block, section, subsection); block = []; section = c; subsection = ""; i = j+1
                    if i < len(lines) and ANY_DIVIDER.match(lines[i].strip()): i += 1
                    continue
            continue
        if SHORT_DASH.match(s): continue
        if re.match(r"^-{2,}\s+[A-Z].*-{0,}$", s):
            flush(block, section, subsection); block = []; subsection = s.strip("- ").strip(); continue
        if BLANK.match(line):
            if block: block.append(line)
            continue
        block.append(line)
    flush(block, section, subsection)
    return rows


SECTION_HEAD_RE = re.compile(r"^SECTION\s+\d+[\.:].+$", re.IGNORECASE)
END_NOISE_RE    = re.compile(r"^(={6,}|-{6,}|END\s+OF\s+(CHEAT\s+)?SHEET)$", re.IGNORECASE)


def is_subheading(line, nxt):
    s = line.strip(); n = (nxt or "").strip()
    if not s or "#" in s or len(s) > 55 or not SUBHEAD_RE.match(s): return False
    return SHORT_DASH.match(n) or n == "" or UNDER_DIVIDER.match(n)


def parse_underline(lines, source):
    rows = []; section = "General"; subsection = ""; block = []; saw_under = False

    def flush(b, sec, sub):
        # Strip trailing decoration lines before storing
        while b and END_NOISE_RE.match(b[-1].strip()):
            b.pop()
        r = make_row(source, sec, sub, b)
        if r: rows.append(r)

    i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip(); i += 1
        if UNDER_DIVIDER.match(s): saw_under = True; continue
        # Match both ALL-CAPS headings and "SECTION N: ..." headings
        if saw_under and (ALL_CAPS_RE.match(s) or SECTION_HEAD_RE.match(s)):
            flush(block, section, subsection)
            block = []; section = s; subsection = ""; saw_under = False; continue
        saw_under = False
        if SHORT_DASH.match(s): continue
        # Skip pure decoration anywhere in content
        if END_NOISE_RE.match(s): continue
        if BLANK.match(line):
            if block: block.append(line)
            continue
        peek = lines[i] if i < len(lines) else ""
        if is_subheading(line, peek):
            flush(block, section, subsection); block = []; subsection = s; continue
        block.append(line)

    flush(block, section, subsection)
    return rows


def looks_like_heading(s):
    if not s or len(s) > 50 or "#" in s: return False
    if CMD_RE.match(s) and ">" not in s and not s[0].isupper(): return False
    return bool(re.match(r"^[A-Z][a-zA-Z &/\-()+]{3,45}$", s) or (ALL_CAPS_RE.match(s) and len(s) <= 50))


def parse_flat(lines, source):
    rows = []; section = source.replace("_"," ").title(); subsection = ""; block = []
    def flush(b,sec,sub):
        r = make_row(source,sec,sub,b)
        if r: rows.append(r)
    i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip(); i += 1
        if EQ_DIVIDER.match(s) or UNDER_DIVIDER.match(s):
            flush(block, section, subsection); block = []; subsection = ""; continue
        if BLANK.match(line):
            if block: block.append(line)
            continue
        if NUMBERED_HEAD.match(s):
            flush(block, section, subsection); block = []; subsection = s; continue
        if looks_like_heading(s):
            flush(block, section, subsection); block = []; subsection = s; continue
        block.append(line)
    flush(block, section, subsection)
    return rows


def parse_file(filepath):
    source = filepath.stem
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        lines = [l.rstrip("\r\n") for l in fh.readlines()]
    fmt = detect_format(lines)
    if fmt == "underline":     return parse_underline(lines, source)
    if fmt == "dash_sections": return parse_dash_sections(lines, source)
    return parse_flat(lines, source)


# ══════════════════════════════════════════════════════════════════════════════
#  JSON PARSER
#  Reads structured .json files from the json/ folder.
#
#  JSON schema (each file):
#  {
#    "source":   "my_topic",          ← used as source name in CSV (required)
#    "category": "Linux",             ← optional hint for topic categorisation
#    "entries": [
#      {
#        "section":    "SECTION 1: MY TOPIC",   ← required
#        "subsection": "DO SOMETHING",          ← optional, default ""
#        "type":       "command",               ← optional: command|steps|prose
#                                                  (auto-detected if omitted)
#        "content":    "line1\nline2\nline3"    ← required, use \n for newlines
#      },
#      ...
#    ]
#  }
#
#  The 'type' field is optional — if omitted the parser auto-detects it
#  the same way it does for .txt files (numbered steps → steps,
#  command-like lines → command, else prose).
#
#  The 'tags' field is always auto-generated; don't include it in JSON.
# ══════════════════════════════════════════════════════════════════════════════

def parse_json_file(filepath: Path) -> list:
    import json

    with open(filepath, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as e:
            print(f"  [WARN] Skipping {filepath.name} — JSON error: {e}")
            return []

    source = data.get("source", filepath.stem)
    entries = data.get("entries", [])

    if not entries:
        print(f"  [WARN] {filepath.name} has no entries — skipped")
        return []

    rows = []
    for i, entry in enumerate(entries):
        section    = entry.get("section", "").strip()
        subsection = entry.get("subsection", "").strip()
        content    = entry.get("content", "").strip()

        if not section or not content:
            print(f"  [WARN] {filepath.name} entry {i+1}: missing section or content — skipped")
            continue

        # Normalise line endings in content
        content = content.replace("\\n", "\n").replace("\r\n", "\n")

        # Auto-detect type if not specified
        explicit_type = entry.get("type", "").strip().lower()
        if explicit_type in ("command", "steps", "prose"):
            entry_type = explicit_type
        else:
            content_lines = content.splitlines()
            entry_type = detect_type(content_lines)

        rows.append({
            "source":     source,
            "section":    section,
            "subsection": subsection,
            "type":       entry_type,
            "content":    content,
            "tags":       make_tags(source, section, subsection, content),
        })

    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  TOPIC GENERATION
#  Scans the CSV and builds topics.json — a dynamic browse menu.
#  Each unique section becomes a topic entry.
#  Category is inferred from source name and section title.
# ══════════════════════════════════════════════════════════════════════════════

# Maps keywords found in source/section names → category label
# First match wins. Add new lines here if you add new subject areas.
CATEGORY_RULES = [
    (["subnet", "subnetting", "cidr", "vlsm", "binary", "ultimatesubnet"],  "Subnetting"),
    (["linux", "dnf", "rpm", "bash", "redhat", "rocky", "bind", "named",
      "zone", "resolv"],                                                     "Linux"),
    (["cisco", "vlan", "ospf", "routing", "acl", "nat"],                    "Cisco / Networking"),
    (["windows", "active directory", "aduc", "adds", "powershell",
      "delegation", "sysprep", "domain", "ou", "organizational",
      "organisational", "quick reference", "important paths",
      "dns", "dhcp", "dc1", "core", "round robin"],                         "Windows Server"),
    (["network", "script", "screenshot", "overview", "pretty"],             "General"),
]

def infer_category(source: str, section: str) -> str:
    blob = (source + " " + section).lower()
    for keywords, label in CATEGORY_RULES:
        if any(k in blob for k in keywords):
            return label
    return "General"


def make_display_name(source: str, section: str) -> str:
    """Turn a raw section string into a readable short menu label."""
    s = section.strip()

    # Strip "SECTION N: SUBJECT - " prefix → keep subject part
    m = re.match(r"^SECTION\s+\d+[.:]\s*(.+)$", s, re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    # Strip leading category prefix like "LINUX - " or "WINDOWS SERVER - "
    s = re.sub(r"^(LINUX|WINDOWS SERVER?|CISCO)\s*[-–]\s*", "", s, flags=re.IGNORECASE)

    # Strip leading number like "1. " or "12. "
    s = re.sub(r"^\d+\.\s+", "", s)

    # Title-case if all caps (but preserve known acronyms)
    KEEP_UPPER = {"CIDR","VLSM","DNS","DHCP","SSH","ACL","NAT","OSPF","RIP",
                  "AD","ADDS","ADUC","ADAC","GUI","CLI","OU","RFC","VMs",
                  "DNF","RPM","SYSVOL","OOBE","VM","APIPA","IP","TCP","UDP"}
    if s == s.upper() and len(s) > 3:
        words = s.split()
        s = " ".join(w if w in KEEP_UPPER else w.title() for w in words)

    # Trim long section names with parenthetical detail
    s = re.sub(r"\s*\(every subnet has these\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\(/24 and smaller\)", "", s, flags=re.IGNORECASE)

    # Replace known non-ASCII symbols with ASCII equivalents
    s = s.replace("↔", "<->").replace("→", "->").replace("←", "<-")
    s = s.replace("≥", ">=").replace("≤", "<=").replace("≠", "!=")
    s = s.replace("×", "x").replace("÷", "/").replace("·", ".")
    # Strip any remaining non-ASCII characters
    s = s.encode("ascii", errors="ignore").decode("ascii").strip()

    return s[:55].strip()


def make_search_query(source: str, section: str) -> str:
    """
    Build the search query for this topic.
    Uses distinctive words from the section name + a category anchor.
    """
    category = infer_category(source, section)
    anchor   = {"Linux": "linux", "Windows Server": "windows",
                "Cisco / Networking": "cisco", "Subnetting": "subnet",
                "General": ""}.get(category, "")

    s = section.strip()
    # Strip section number prefix
    s = re.sub(r"^SECTION\s+\d+[.:]\s*", "", s, flags=re.IGNORECASE)
    # Strip category prefix
    s = re.sub(r"^(LINUX|WINDOWS SERVER?|CISCO)\s*[-–]\s*", "", s, flags=re.IGNORECASE)
    # Strip leading number like "1. "
    s = re.sub(r"^\d+\.\s+", "", s)

    query_stop = {
        "the","and","for","with","gui","all","important","quick","misc",
        "using","tools","commands","management","reference","overview",
        "introduction","basics","general","information","notes","from","slides",
    }
    words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", s)
             if w.lower() not in query_stop and len(w) >= 3]

    # Take up to 3 most distinctive words
    query_words = words[:3]
    if anchor and anchor not in query_words:
        query_words.insert(0, anchor)

    # Fallback: use anchor + source name words
    if not query_words:
        src_words = [w for w in source.replace("_"," ").split() if w not in query_stop]
        query_words = ([anchor] if anchor else []) + src_words[:2]

    return " ".join(query_words)


def generate_topics(rows: list, out_path: Path):
    import json

    # Collect unique (source, section) pairs in order of first appearance
    seen   = set()
    topics = []   # list of {category, display, query, source, section}

    for row in rows:
        key = (row["source"], row["section"])
        if key in seen:
            continue
        seen.add(key)

        source  = row["source"]
        section = row["section"]

        # Skip meaningless catch-all sections
        if section.strip().lower() in ("general", ""):
            continue

        # Skip sections that look like content rather than headings:
        # - Too short (less than 4 chars)
        # - Starts with punctuation/symbol (e.g. "And (&):", "---", "* note")
        # - Only contains symbols/numbers (no letters at all)
        s = section.strip()
        if len(s) < 4:
            continue
        if not re.search(r"[a-zA-Z]", s):
            continue
        if re.match(r"^[^a-zA-Z0-9]", s):
            continue
        # Skip if it looks like a sentence fragment / bitwise op / operator label
        if re.match(r"^(AND|OR|XOR|NOT|Left|Right)\s*[\(&\|^~<>]", s):
            continue

        category = infer_category(source, section)
        display  = make_display_name(source, section)
        query    = make_search_query(source, section)

        topics.append({
            "category": category,
            "display":  display,
            "query":    query,
            "source":   source,
            "section":  section,
        })

    # Group by category preserving insertion order
    from collections import OrderedDict
    grouped: dict = OrderedDict()
    for t in topics:
        grouped.setdefault(t["category"], []).append(t)

    output = {"categories": []}
    for cat, items in grouped.items():
        output["categories"].append({
            "name":   cat,
            "topics": items,
        })

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False)

    total = sum(len(c["topics"]) for c in output["categories"])
    print(f"  topics.json  —  {total} topics in {len(output['categories'])} categories")
    return total


# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate knowledge_base.csv from .txt and .json files")
    ap.add_argument("--txt",    default="txt",                help="Folder with .txt files   (default: ./txt)")
    ap.add_argument("--json",   default="json",               help="Folder with .json files  (default: ./json)")
    ap.add_argument("--out",    default="knowledge_base.csv", help="Output CSV path")
    ap.add_argument("--topics", default="topics.json",        help="Output topics JSON path")
    args = ap.parse_args()

    all_rows = []

    # ── Parse .txt files ───────────────────────────────────────────────────
    txt_folder = Path(args.txt)
    txt_files  = sorted(txt_folder.glob("*.txt")) if txt_folder.exists() else []

    if txt_files:
        print(f"\nParsing .txt files from {txt_folder.resolve()}/\n")
        for fp in txt_files:
            rows = parse_file(fp)
            all_rows.extend(rows)
            print(f"  {fp.name:45s}  {len(rows):3d} entries")
    elif txt_folder.exists():
        print(f"\n  [txt] No .txt files found in {txt_folder.resolve()}/  — skipped")
    else:
        print(f"\n  [txt] Folder not found: {txt_folder.resolve()}/  — skipped")

    # ── Parse .json files ──────────────────────────────────────────────────
    json_folder = Path(args.json)
    # Exclude the output topics.json if it lives in the same folder
    json_files  = [f for f in sorted(json_folder.glob("*.json"))
                   if f.resolve() != Path(args.topics).resolve()
                   and f.name != "topics.json"
                   and not f.name.startswith("_")] if json_folder.exists() else []

    if json_files:
        print(f"\nParsing .json files from {json_folder.resolve()}/\n")
        for fp in json_files:
            rows = parse_json_file(fp)
            all_rows.extend(rows)
            print(f"  {fp.name:45s}  {len(rows):3d} entries")
    elif json_folder.exists():
        print(f"\n  [json] No .json files in {json_folder.resolve()}/  — skipped")
    else:
        print(f"\n  [json] Folder not found: {json_folder.resolve()}/  — skipped")

    if not all_rows:
        print("\n  [ERROR] No entries found. Check your txt/ and json/ folders."); return

    # ── Write CSV ──────────────────────────────────────────────────────────
    out_path = Path(args.out)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source","section","subsection","type","content","tags"])
        writer.writeheader()
        writer.writerows(all_rows)

    note = "with nltk NLP" if NLP_AVAILABLE else "without nltk (install it for richer tags)"
    print(f"\n[OK] {len(all_rows)} total entries written {note}")
    print(f"     {out_path.resolve()}")

    # ── Write topics.json ──────────────────────────────────────────────────
    topics_path = Path(args.topics)
    generate_topics(all_rows, topics_path)
    print(f"     {topics_path.resolve()}\n")
    print("Distribute to other PCs:")
    print("  knowledge_base.csv  +  topics.json  +  search_kb.ps1  +  kb.bat\n")


if __name__ == "__main__":
    main()