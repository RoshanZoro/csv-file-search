"""
main.py  –  v10
================
Run ONCE at home to generate knowledge_base.csv from your .txt / .json files.

Install dependencies first:
    pip install nltk scikit-learn rapidfuzz

v10 changes vs v9:
    ┌─────────────────────────────────────────────────────────────────┐
    │  NEW: TF-IDF weight column                                      │
    │    Each entry gets a float 'weight' (0.0–1.0) baked into the   │
    │    CSV. Rare, specific terms score high; common filler terms    │
    │    score low. PowerShell multiplies the score by this weight    │
    │    so 'restorecon' beats 'windows configure' in ranking.        │
    │                                                                 │
    │  NEW: Entry quality score                                       │
    │    Additional bonus weight for entries that are:                │
    │      - type=command or steps (+bonus)                           │
    │      - have a meaningful subsection (+bonus)                    │
    │      - have content > 10 lines (+bonus)                         │
    │    Practical reference material floats above background prose.  │
    │                                                                 │
    │  NEW: N-gram tag extraction (sklearn TfidfVectorizer)           │
    │    Extracts the most distinctive 1–3 word phrases per entry     │
    │    using TF-IDF across the whole corpus. These become bonus     │
    │    tags that regular keyword matching would miss, e.g.:         │
    │      "ip helper-address", "easy-rsa pki", "passive-interface"   │
    │    Falls back gracefully if sklearn not installed.              │
    │                                                                 │
    │  NEW: Co-occurrence compound tags                               │
    │    Terms that appear together in the same entry get a compound  │
    │    tag injected: e.g. content with both "ospf" and "passive"    │
    │    gets tag "ospf passive", making phrase queries more precise. │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    python main.py
    python main.py --txt txt/ --json json/ --out knowledge_base.csv
"""

import re, csv, math
from pathlib import Path
from collections import Counter, defaultdict

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
    print("  [warn] nltk not found — continuing with built-in tags")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
    print("  [sklearn] TF-IDF n-gram extraction enabled")
except ImportError:
    SKLEARN_AVAILABLE = False
    print("  [warn] sklearn not found — install with: pip install scikit-learn")
    print("         Continuing without n-gram extraction (still works fine).")

# ══════════════════════════════════════════════════════════════════════════════
#  CURATED KEYWORD TABLES
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_KEYWORDS: dict = {
    "user_cheat_sheet": [
        "linux","windows","user","group","sudo","package","organisational","ou",
        "desktop","pc","client","computer","join","domain","active","directory",
        "ad","adds","aduc","powershell","delegation","sysprep","config","management",
        "unix","shell","bash","rocky","redhat","rhel",
        "users","account","useradd","adduser","userdel","usermod",
        "groups","groupadd","groupmod","groupdel",
        "password","passwd","shadow","chage","lock","unlock","expire","aging",
        "sudoers","visudo","root","wheel","privilege","admin",
        "dnf","rpm","yum","install","remove","upgrade",
        "configuration","skel","profile","reference",
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
    "directory_services_part1": [
        "windows","active","directory","ad","adds","domain","dc","domain controller",
        "create","install","setup","promote","forest","rras","router","vyos",
        "rip","routing","nat","dhcp","linux","rocky","virtual","lab","vm",
        "school.test","bmc.test","server","client","join",
    ],
    "windows_ad_directory_services": [
        "windows","active","directory","ad","adds","domain","dc","domain controller",
        "create","install","setup","promote","forest","aduc","adac","ou",
        "organizational","unit","user","group","password","policy","gpo",
        "dhcp","dns","failover","scope","rras","server","school.test",
    ],
    "windows_group_policies": [
        "windows","group","policy","gpo","aduc","adac","ou","domain",
        "baseline","security","kiosk","folder","redirection","software",
        "deploy","admx","template","office","loopback","inheritance","enforce",
        "school.test","dc1","pc1","pc2",
    ],
    "windows_security_pki": [
        "windows","pki","ca","certificate","authority","adcs","ipsec",
        "firewall","isolation","server","domain","vpn","sstp","tls","ssl",
        "enrollment","auto","template","crl","gpo","school.test","rras1",
    ],
    "vpn_windows_linux": [
        "vpn","windows","linux","pptp","sstp","l2tp","ikev2","openvpn","wireguard",
        "rras","nps","certificate","tls","ssl","tunnel","remote","access",
        "easy-rsa","pki","ca","client","server","school.test","bmc.test",
        "authentication","mschapv2","eap","radius","port","forwarding","vyos",
    ],
    "linux_mail_services": [
        "linux","mail","postfix","dovecot","smtp","imap","pop3","mta","mua",
        "email","thunderbird","evolution","mailx","tls","ssl","certificate",
        "dns","mx","record","bind","alias","firewall","rocky","bmc.test",
        "sasl","starttls","selinux","restorecon",
    ],
    "linux_storage_lvm_raid": [
        "linux","storage","lvm","raid","disk","partition","volume","group",
        "logical","physical","extend","resize","snapshot","mdadm","pv","vg","lv",
        "mount","filesystem","xfs","ext4","fstab","rocky",
    ],
    "acl_nat_pat": [
        "cisco","acl","nat","pat","access","list","permit","deny","overload",
        "inside","outside","interface","dhcp","pool","wildcard","internet",
        "translation","ip","filter","extended","standard","router",
    ],
    "ospf_acl_dynamic_routing": [
        "cisco","ospf","acl","routing","dynamic","area","passive","interface",
        "access","list","permit","deny","wildcard","redistribute","static",
        "ipv6","ospfv3","ripng","extended","standard",
    ],
    "routing_rip_ospf": [
        "cisco","rip","ospf","routing","static","floating","loopback","serial",
        "redistribute","default","route","area","passive","interface",
        "ipv4","ipv6","ripng","ospfv3","acl","access","list",
    ],
    "intervlan_routing_ipv6": [
        "cisco","vlan","intervlan","routing","router","stick","subinterface",
        "ospf","rip","ripng","ipv6","dhcp","helper","address","trunk","dot1q",
        "ssh","crypto","rsa","loopback",
    ],
    "subnetting_ospf_intervlan": [
        "subnet","subnetting","ospf","intervlan","vlan","routing","serial",
        "cidr","mask","network","host","area","static","route","cisco",
    ],
}

SECTION_KEYWORDS: dict = {
    "user & group":            ["linux","user","group","useradd","userdel","usermod","groupadd","groupdel","management","account"],
    "linux - user":            ["linux","user","useradd","userdel","usermod","adduser","account"],
    "linux - package":         ["linux","package","dnf","install","remove","upgrade","rpm"],
    "package management":      ["linux","package","dnf","rpm","install","remove","upgrade","group"],
    "sudo":                    ["linux","sudo","root","admin","privilege","wheel","visudo","sudoers"],
    "permissions":             ["linux","sudo","chmod","chown","permission","rights","privilege"],
    "config files":            ["linux","config","passwd","shadow","sudoers","skel","group","reference","paths"],
    "verification":            ["linux","verify","check","id","rpm","query","man"],
    "password":                ["linux","windows","password","passwd","chage","expire","lock","aging","policy"],
    "active directory":        ["windows","active","directory","ad","adds","domain","install","setup","configure","dc","domain controller","create","promote","forest"],
    "active directory setup":  ["windows","active","directory","ad","adds","domain","install","setup","gui","promote","dc","forest","domain controller","create"],
    "domain controller":       ["windows","domain","controller","promote","dc","forest","adds","roles","active","directory","create","install","setup"],
    "promote":                 ["windows","domain","controller","promote","dc","forest","adds","active","directory"],
    "create active directory":  ["windows","active","directory","ad","adds","domain","promote","dc","forest","install","setup","create","domain controller"],
    "organisational":          ["windows","ou","organisational","organizational","unit","aduc","adac","container","create","active","directory"],
    "organizational":          ["windows","ou","organisational","organizational","unit","aduc","adac","container","create","active","directory"],
    "user management":         ["windows","user","aduc","adac","template","copy","profile","home","folder","create","disable","active","directory"],
    "powershell":              ["windows","powershell","cmdlet","new-aduser","import-csv","module","script","bulk","active","directory"],
    "command line ad":         ["windows","dsadd","dsmod","dsquery","dsmove","csvde","ldifde","cli","command","line","active","directory"],
    "delegation":              ["windows","delegate","delegation","control","permission","rights","wizard","ou","active","directory"],
    "sysprep":                 ["windows","sysprep","clone","linked","generalize","oobe","vm","vmware","snapshot"],
    "quick reference":         ["paths","reference","etc","windows","linux","sysvol","roaming","homefolder","important"],
    "join":                    ["windows","join","domain","client","pc","desktop","computer","workstation","machine"],
    "windows client":          ["windows","join","domain","client","pc","desktop","computer","workstation","machine"],
    "pki":                     ["windows","pki","ca","certificate","authority","adcs","install","setup","template","enrollment","tls","ssl"],
    "certificate":             ["windows","certificate","ca","pki","adcs","template","auto","enrollment","tls","ssl","crl"],
    "ipsec":                   ["windows","ipsec","firewall","isolation","server","domain","policy","rule"],
    "server isolation":        ["windows","ipsec","isolation","firewall","policy","server","domain","rule"],
    "domain isolation":        ["windows","ipsec","isolation","firewall","policy","domain","rule"],
    "vpn":                     ["vpn","windows","linux","pptp","sstp","l2tp","ikev2","openvpn","wireguard","tunnel","remote","access"],
    "pptp":                    ["vpn","pptp","windows","rras","nps","authentication","mschapv2","port","1723"],
    "sstp":                    ["vpn","sstp","windows","certificate","tls","ssl","rras","port","443"],
    "openvpn":                 ["vpn","openvpn","linux","easy-rsa","pki","ca","certificate","tls","udp","1194","rocky"],
    "wireguard":               ["vpn","wireguard","linux","modern","udp","51820","peer","public","key"],
    "postfix":                 ["linux","postfix","smtp","mail","mta","configure","main.cf","master.cf","relay","sasl"],
    "dovecot":                 ["linux","dovecot","imap","pop3","access","agent","maildir","ssl","authentication"],
    "mail":                    ["linux","mail","smtp","imap","pop3","mta","mua","postfix","dovecot","email"],
    "smtp":                    ["linux","smtp","postfix","mail","port","25","relay","sasl","tls","starttls"],
    "tls encryption":          ["linux","tls","ssl","certificate","starttls","postfix","dovecot","encrypt","secure","mail"],
    "lvm":                     ["linux","lvm","logical","volume","pv","vg","lv","extend","resize","snapshot","disk"],
    "raid":                    ["linux","raid","mdadm","array","mirror","stripe","disk","redundancy","fault"],
    "storage":                 ["linux","storage","disk","partition","lvm","raid","mount","filesystem","fstab"],
    "vlan":                    ["cisco","vlan","trunk","access","switchport","allowed","port","mode"],
    "routing":                 ["cisco","routing","route","ospf","rip","static","default","gateway","table"],
    "ssh":                     ["cisco","ssh","crypto","rsa","transport","vty","login","local","secure","remote"],
    "acl":                     ["cisco","acl","access","list","permit","deny","filter","wildcard","inbound","outbound"],
    "nat":                     ["cisco","nat","translation","inside","outside","overload","masquerade","pat"],
    "dhcp":                    ["cisco","dhcp","pool","network","router","dns","lease","default"],
    "ospf":                    ["cisco","ospf","area","passive","interface","redistribute","static","routing","dynamic"],
    "rip":                     ["cisco","rip","routing","dynamic","update","timers","version","redistribute"],
    "intervlan":               ["cisco","intervlan","vlan","routing","subinterface","dot1q","encapsulation","router","stick"],
    "the basics":              ["subnet","subnetting","basics","ipv4","network","host","mask","portion","split"],
    "slash notation":          ["subnet","cidr","slash","notation","prefix","bits","ones","zeros"],
    "special addresses":       ["subnet","special","network","broadcast","usable","first","last","formula"],
    "formula":                 ["subnet","formula","block","size","calculate","usable","hosts","256"],
    "reference table":         ["subnet","reference","table","hosts","block","size","subnets","cidr"],
    "picking the right":       ["subnet","pick","choose","size","hosts","needed","fit","requirements"],
    "splitting":               ["subnet","split","divide","example","27","subnets","block","network"],
    "vlsm":                    ["subnet","vlsm","variable","length","efficient","assign","allocate","largest","first","steps"],
    "private ip":              ["subnet","private","ip","rfc","1918","range","internal","class","not","routable"],
    "special address":         ["subnet","special","loopback","apipa","broadcast","default","route","unspecified"],
    "binary":                  ["subnet","binary","decimal","convert","bits","octet","position","value","hex"],
    "quick cheat":             ["subnet","quick","card","reference","summary","formula","vlsm"],
}

SYNONYMS: dict = {
    "add":              ["create","new","useradd","adduser","install","join","make"],
    "create":           ["add","new","make","useradd","adduser","setup","configure","install","build"],
    "remove":           ["delete","del","userdel","uninstall","erase","drop"],
    "delete":           ["remove","del","userdel","erase","drop"],
    "install":          ["add","setup","deploy","enable","dnf","apt","rpm","configure"],
    "configure":        ["config","setup","set","customise","customize","edit","change"],
    "enable":           ["activate","allow","permit","start"],
    "disable":          ["lock","deactivate","prevent","block"],
    "lock":             ["disable","block","usermod","prevent","deactivate"],
    "unlock":           ["enable","unblock","activate","usermod"],
    "show":             ["display","list","view","check","get","verify","print"],
    "join":             ["connect","add","domain","member","client","desktop","pc","computer"],
    "promote":          ["dc","controller","domain","adds","forest","roles","active directory","create dc"],
    "setup":            ["configure","install","create","build","deploy","initialize"],
    "user":             ["users","account","useradd","adduser","userdel","usermod","person","login","new-aduser"],
    "group":            ["groups","groupadd","groupmod","groupdel","member","membership","security group"],
    "password":         ["passwd","chage","secret","credentials","pass","pwd"],
    "active directory": ["ad","adds","domain","dc","domain controller","aduc","adac","forest","school.test","windows server"],
    "ad":               ["active directory","adds","domain","dc","domain controller","aduc","forest"],
    "adds":             ["active directory","ad","domain","dc","domain controller","promote","forest","install"],
    "domain":           ["ad","active directory","forest","dc","join","client","computer","adds","school.test"],
    "domain controller":["dc","promote","adds","forest","active directory","install","setup","create"],
    "dc":               ["domain controller","promote","adds","forest","active directory"],
    "aduc":             ["active directory","adac","ou","user","management","windows","domain"],
    "adac":             ["active directory","aduc","ou","user","management","windows","domain"],
    "ou":               ["organisational","organizational","unit","container","aduc","adac","active directory"],
    "organisational":   ["ou","organizational","unit","container","aduc","create","active directory"],
    "organizational":   ["ou","organisational","unit","container","aduc","create","active directory"],
    "forest":           ["domain","active directory","adds","dc","domain controller","promote"],
    "gpo":              ["group policy","policy","windows","aduc","ou","baseline","security"],
    "group policy":     ["gpo","policy","windows","aduc","ou","baseline","security","configure"],
    "desktop":          ["pc","computer","client","workstation","machine","join","windows","domain"],
    "pc":               ["desktop","computer","client","workstation","machine"],
    "computer":         ["pc","desktop","client","workstation","machine","join","domain"],
    "client":           ["pc","desktop","computer","workstation","join","domain","windows"],
    "pki":              ["ca","certificate authority","adcs","certificate","tls","ssl","enrollment","template"],
    "ca":               ["certificate authority","pki","adcs","certificate","tls","ssl","root ca","enterprise ca"],
    "certificate":      ["ca","pki","tls","ssl","adcs","crt","key","csr","enrollment","template","openssl"],
    "tls":              ["ssl","certificate","ca","pki","encrypt","secure","starttls","https"],
    "ssl":              ["tls","certificate","ca","pki","encrypt","secure","openssl"],
    "vpn":              ["virtual private network","tunnel","remote access","pptp","sstp","l2tp","ikev2","openvpn","wireguard","rras"],
    "pptp":             ["vpn","rras","windows","point to point","tunnel","mschapv2","port 1723"],
    "sstp":             ["vpn","ssl","tls","certificate","rras","windows","port 443","secure tunnel"],
    "openvpn":          ["vpn","linux","ssl","tls","easy-rsa","pki","certificate","udp 1194","rocky","open vpn"],
    "wireguard":        ["vpn","linux","modern","fast","udp 51820","peer","public key","simple"],
    "rras":             ["routing","remote access","windows","vpn","nat","router","server"],
    "postfix":          ["mail","smtp","mta","email","linux","configure","main.cf","relay"],
    "dovecot":          ["mail","imap","pop3","access agent","linux","maildir","ssl"],
    "smtp":             ["mail","postfix","email","port 25","relay","send","mta"],
    "imap":             ["mail","dovecot","email","port 143","receive","inbox","imaps"],
    "pop3":             ["mail","dovecot","email","port 110","receive","download","pop3s"],
    "email":            ["mail","smtp","imap","pop3","postfix","dovecot","mta","mua"],
    "mx":               ["mail","dns","mx record","exchange","postfix","email"],
    "lvm":              ["logical volume","pv","vg","lv","extend","resize","disk","storage","snapshot"],
    "raid":             ["mdadm","mirror","stripe","array","disk","redundancy","fault tolerance","storage"],
    "partition":        ["disk","storage","fdisk","parted","lvm","mount","filesystem"],
    "interface":        ["fastethernet","gigabit","fa","gi","eth","port","nic","int"],
    "vlan":             ["trunk","access","switchport","lan","virtual","network"],
    "trunk":            ["uplink","inter","vlan","allowed","switchport","mode"],
    "router":           ["routing","ospf","rip","route","gateway","default"],
    "routing":          ["route","ospf","rip","router","static","dynamic","table"],
    "ospf":             ["routing","dynamic","area 0","passive","redistribute","link state"],
    "rip":              ["routing","dynamic","distance vector","update","version 2"],
    "acl":              ["access list","permit","deny","filter","wildcard","control"],
    "nat":              ["translation","inside","outside","overload","masquerade","pat"],
    "subnet":           ["subnetting","cidr","mask","vlsm","prefix","ip","network"],
    "subnetting":       ["subnet","cidr","mask","vlsm","prefix","ip","calculate","network"],
    "mask":             ["subnet","cidr","netmask","prefix","255","slash"],
    "vlsm":             ["variable","length","subnet","mask","subnetting","efficient","assign"],
    "cidr":             ["slash","prefix","notation","mask","subnet","bits"],
    "ip":               ["address","subnet","cidr","host","network","dhcp","ipv4"],
    "dhcp":             ["ip","address","lease","pool","network","dns","router"],
    "cisco":            ["router","switch","networking","commands","ios"],
    "linux":            ["unix","bash","shell","dnf","rpm","sudo","rocky","redhat","rhel"],
    "windows":          ["server","win","microsoft","ad","domain","active directory"],
    "sudo":             ["root","admin","privilege","superuser","wheel","escalate","visudo"],
    "package":          ["dnf","apt","rpm","install","software","program","module"],
    "sysprep":          ["clone","linked","generalize","oobe","vm","vmware","snapshot","image"],
    "delegate":         ["permission","rights","control","assign","wizard","ou","grant"],
    "ssh":              ["secure","remote","login","telnet","crypto","rsa","transport","vty"],
    "firewall":         ["firewall-cmd","iptables","port","allow","block","rule","zone","permanent"],
    "selinux":          ["restorecon","semanage","chcon","context","label","enforcing","permissive"],
}

SKIP_SECTIONS = {
    "submission requirements","what to submit","if assignment did not succeed",
    "assessment criteria","required screenshots","required demonstrations",
    "required demo","sign-off criteria","sign off criteria","screenshot commands",
    "snapshots","lab assignment","submission",
}

def is_noise_section(section: str, subsection: str) -> bool:
    blob = (section + " " + subsection).lower()
    return any(k in blob for k in SKIP_SECTIONS)

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


# ══════════════════════════════════════════════════════════════════════════════
#  CO-OCCURRENCE COMPOUND TAG EXTRACTION
#  Terms that appear together in the same entry get a compound tag injected.
#  e.g. content with "ospf" + "passive" → adds tag "ospf passive"
#  These phrases are more specific than individual terms, so they match
#  multi-word queries much more precisely.
# ══════════════════════════════════════════════════════════════════════════════

# Pairs of terms that are meaningful together
COMPOUND_PAIRS = [
    ("ospf","passive"),    ("ospf","area"),      ("ospf","redistribute"),
    ("ospf","interface"),  ("rip","redistribute"),("nat","overload"),
    ("nat","inside"),      ("nat","outside"),     ("ip","helper"),
    ("ip","route"),        ("access","list"),     ("acl","extended"),
    ("acl","standard"),    ("vlan","trunk"),      ("vlan","access"),
    ("dot1q","encapsulation"), ("crypto","rsa"),  ("ssh","vty"),
    ("lvm","extend"),      ("lvm","snapshot"),    ("raid","mdadm"),
    ("pki","certificate"), ("tls","starttls"),    ("easy-rsa","ca"),
    ("postfix","main.cf"), ("dovecot","imap"),    ("firewall","cmd"),
    ("active","directory"),("domain","controller"),("group","policy"),
    ("ou","aduc"),         ("sysprep","generalize"),("ip","dhcp"),
    ("subnet","mask"),     ("cidr","prefix"),     ("vlsm","assign"),
    ("binary","decimal"),  ("default","route"),   ("floating","static"),
    ("passive","interface"),("loopback","interface"),
]

def extract_compound_tags(content: str) -> list:
    """Return compound tags for term pairs that both appear in content."""
    words = set(re.findall(r"[a-z][a-z0-9\-]{1,}", content.lower()))
    compounds = []
    for a, b in COMPOUND_PAIRS:
        if a in words and b in words:
            compounds.append(f"{a} {b}")
    return compounds


# ══════════════════════════════════════════════════════════════════════════════
#  MAKE TAGS
# ══════════════════════════════════════════════════════════════════════════════

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
        for pfx in ("user","group","net","fast","get","ip","no","show"):
            if w.startswith(pfx) and len(w) > len(pfx) + 2:
                add(w[len(pfx):])

    # 4. Co-occurrence compound tags
    for compound in extract_compound_tags(f"{section} {subsection} {content}"):
        if compound not in seen:
            seen.add(compound)
            tags.append(compound)

    return ",".join(tags[:180])


# ══════════════════════════════════════════════════════════════════════════════
#  JSON SOURCE AUTO-REGISTRATION
# ══════════════════════════════════════════════════════════════════════════════

_CATEGORY_SEED_KEYWORDS: dict = {
    "Linux": [
        "linux","unix","bash","shell","rocky","redhat","rhel","dnf","rpm",
        "sudo","root","configure","install","service","systemctl","firewall",
    ],
    "Windows Server": [
        "windows","server","microsoft","active","directory","ad","adds","domain",
        "dc","domain controller","aduc","adac","ou","powershell","gpo","group policy",
        "configure","install","setup",
    ],
    "Cisco / Networking": [
        "cisco","router","switch","networking","interface","vlan","trunk",
        "routing","ospf","rip","acl","nat","dhcp","ssh","configure","show",
    ],
    "Subnetting": [
        "subnet","subnetting","cidr","mask","prefix","slash","ip","ipv4",
        "host","network","broadcast","vlsm","block","calculate",
    ],
    "General": [],
}

def _register_json_source(source: str, category: str):
    if source not in SOURCE_KEYWORDS:
        seeds = list(_CATEGORY_SEED_KEYWORDS.get(category, []))
        for w in re.findall(r"[a-z]{3,}", source.replace("_", " ")):
            if w not in seeds:
                seeds.append(w)
        SOURCE_KEYWORDS[source] = seeds


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY QUALITY WEIGHT
#  Returns a float 0.0–1.0 that reflects how "useful" an entry is.
#  Baked into the CSV so PowerShell can use it at search time with zero effort.
#
#  Scoring:
#    base                  = 0.40
#    type = command        + 0.20
#    type = steps          + 0.15
#    has non-empty subsec  + 0.15
#    content > 10 lines    + 0.10
#    content > 5  lines    + 0.05
#    section is ALL CAPS   + 0.05   (structured source = more reliable)
# ══════════════════════════════════════════════════════════════════════════════

def entry_quality(row: dict) -> float:
    score = 0.40
    if row["type"] == "command":             score += 0.20
    elif row["type"] == "steps":             score += 0.15
    if row["subsection"].strip():            score += 0.15
    lines = row["content"].count("\n") + 1
    if lines > 10:                           score += 0.10
    elif lines > 5:                          score += 0.05
    if row["section"] == row["section"].upper() and len(row["section"]) > 3:
        score += 0.05
    return round(min(score, 1.0), 3)


# ══════════════════════════════════════════════════════════════════════════════
#  TF-IDF WEIGHT (computed corpus-wide, baked into CSV)
#
#  Strategy:
#    1. Build a "document" per entry = section + subsection + tags + content
#    2. Fit TfidfVectorizer on all documents
#    3. For each entry, take the mean TF-IDF score of its top-N terms
#    4. Normalise to 0.0–1.0 across the corpus
#    5. Combine with quality score: final_weight = 0.6 * tfidf + 0.4 * quality
#
#  Effect: entries about rare/specific topics (sstp, restorecon, easy-rsa)
#  get higher weight than entries full of common words (windows, configure).
#  PowerShell multiplies the raw match score by this weight before ranking.
# ══════════════════════════════════════════════════════════════════════════════

def compute_weights(rows: list) -> list:
    """
    Adds a 'weight' field (float 0.0–1.0) to each row dict.
    Returns the same list with weights filled in.
    """
    # Always compute quality scores
    for row in rows:
        row["_quality"] = entry_quality(row)

    if not SKLEARN_AVAILABLE:
        # Fallback: weight = quality score only
        for row in rows:
            row["weight"] = row.pop("_quality")
        print(f"  [weight] Quality-only weights applied ({len(rows)} entries)")
        return rows

    # Build corpus documents
    corpus = []
    for row in rows:
        doc = f"{row['section']} {row['subsection']} {row['tags']} {row['content']}"
        corpus.append(doc.lower())

    # Fit TF-IDF — use 1–2 grams, ignore very common and very rare terms
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_df=0.85,        # ignore terms appearing in >85% of entries (too common)
        min_df=2,           # ignore terms appearing in only 1 entry (too rare to help)
        sublinear_tf=True,  # log(1+tf) instead of raw tf — dampens very frequent terms
        max_features=8000,
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)

    # For each entry: mean of its top-10 TF-IDF scores
    raw_scores = []
    for i in range(len(rows)):
        row_vec = tfidf_matrix[i].toarray()[0]
        top_vals = sorted(row_vec[row_vec > 0], reverse=True)[:10]
        raw_scores.append(float(sum(top_vals) / len(top_vals)) if top_vals else 0.0)

    # Normalise TF-IDF scores to 0–1
    max_s = max(raw_scores) if max(raw_scores) > 0 else 1.0
    tfidf_norm = [s / max_s for s in raw_scores]

    # Final weight = 60% TF-IDF specificity + 40% entry quality
    for i, row in enumerate(rows):
        q = row.pop("_quality")
        row["weight"] = round(0.6 * tfidf_norm[i] + 0.4 * q, 4)

    mn = min(r["weight"] for r in rows)
    mx = max(r["weight"] for r in rows)
    avg = sum(r["weight"] for r in rows) / len(rows)
    print(f"  [weight] TF-IDF+quality weights applied — min={mn:.3f} avg={avg:.3f} max={mx:.3f}")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  N-GRAM BONUS TAGS (sklearn TfidfVectorizer, run once per corpus)
#
#  Extracts the most distinctive 2–3 word phrases per entry and appends
#  them to the tags field. These are phrases TF-IDF finds uniquely important
#  for each entry — things like "ip helper-address", "easy-rsa pki",
#  "passive-interface default" that curated keywords would never capture.
# ══════════════════════════════════════════════════════════════════════════════

def inject_ngram_tags(rows: list) -> list:
    """
    Appends up to 8 distinctive n-gram phrases to each row's tags.
    Modifies rows in-place. Returns the same list.
    """
    if not SKLEARN_AVAILABLE:
        return rows

    corpus = [
        f"{r['section']} {r['subsection']} {r['content']}".lower()
        for r in rows
    ]

    # 2–3 word phrases only (1-grams already handled by make_tags)
    vec = TfidfVectorizer(
        ngram_range=(2, 3),
        max_df=0.7,
        min_df=2,
        sublinear_tf=True,
        max_features=6000,
        token_pattern=r"[a-z][a-z0-9\-]{1,}",  # allow hyphenated terms
    )

    try:
        tfidf_matrix = vec.fit_transform(corpus)
    except ValueError:
        # Not enough data for n-gram extraction
        return rows

    feature_names = vec.get_feature_names_out()
    added_total = 0

    for i, row in enumerate(rows):
        row_vec = tfidf_matrix[i].toarray()[0]
        # Get indices of top-8 non-zero features
        top_idx = sorted(
            (idx for idx in range(len(row_vec)) if row_vec[idx] > 0),
            key=lambda idx: row_vec[idx],
            reverse=True
        )[:8]

        bonus = [feature_names[idx] for idx in top_idx]
        if bonus:
            existing = row["tags"]
            new_tags  = ",".join(t for t in bonus if t not in existing)
            if new_tags:
                row["tags"] = f"{existing},{new_tags}" if existing else new_tags
                added_total += len(bonus)

    print(f"  [ngram]  Added {added_total} n-gram bonus tags across {len(rows)} entries")
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  PARSING  (unchanged from v9)
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
    if is_noise_section(section, subsection): return None
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
        while b and END_NOISE_RE.match(b[-1].strip()): b.pop()
        r = make_row(source, sec, sub, b)
        if r: rows.append(r)
    i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip(); i += 1
        if UNDER_DIVIDER.match(s): saw_under = True; continue
        if saw_under and (ALL_CAPS_RE.match(s) or SECTION_HEAD_RE.match(s)):
            flush(block, section, subsection)
            block = []; section = s; subsection = ""; saw_under = False; continue
        saw_under = False
        if SHORT_DASH.match(s): continue
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

def merge_thin_entries(rows: list, min_content_len: int = 80) -> list:
    if not rows: return rows
    merged = [rows[0]]
    for row in rows[1:]:
        prev = merged[-1]
        same_section = row["section"] == prev["section"]
        this_short   = len(row["content"]) < min_content_len
        no_sub       = not row["subsection"].strip()
        prev_no_sub  = not prev["subsection"].strip()
        if same_section and this_short and no_sub and prev_no_sub:
            prev["content"] = prev["content"] + "\n" + row["content"]
            prev["type"] = detect_type(prev["content"].splitlines())
            prev["tags"] = make_tags(prev["source"], prev["section"], prev["subsection"], prev["content"])
        else:
            merged.append(row)
    return merged

def parse_file(filepath):
    source = filepath.stem
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        lines = [l.rstrip("\r\n") for l in fh.readlines()]
    fmt = detect_format(lines)
    if fmt == "underline":       rows = parse_underline(lines, source)
    elif fmt == "dash_sections": rows = parse_dash_sections(lines, source)
    else:                        rows = parse_flat(lines, source)
    return merge_thin_entries(rows)

def parse_json_file(filepath: Path) -> list:
    import json
    with open(filepath, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as e:
            print(f"  [WARN] Skipping {filepath.name} — JSON error: {e}"); return []
    source   = data.get("source", filepath.stem)
    category = data.get("category", "General").strip()
    entries  = data.get("entries", [])
    if not entries:
        print(f"  [WARN] {filepath.name} has no entries — skipped"); return []
    _register_json_source(source, category)
    rows = []
    for i, entry in enumerate(entries):
        section    = entry.get("section", "").strip()
        subsection = entry.get("subsection", "").strip()
        content    = entry.get("content", "").strip()
        if not section or not content:
            print(f"  [WARN] {filepath.name} entry {i+1}: missing section or content — skipped"); continue
        if is_noise_section(section, subsection): continue
        content = content.replace("\\n", "\n").replace("\r\n", "\n")
        explicit_type = entry.get("type", "").strip().lower()
        entry_type = explicit_type if explicit_type in ("command","steps","prose") else detect_type(content.splitlines())
        rows.append({
            "source": source, "section": section, "subsection": subsection,
            "type": entry_type, "content": content,
            "tags": make_tags(source, section, subsection, content),
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
#  TOPIC GENERATION  (unchanged from v9)
# ══════════════════════════════════════════════════════════════════════════════

SOURCE_CATEGORY_OVERRIDES: dict = {
    "linux cheat sheet":"Linux","networking cheat sheet":"Windows Server",
    "user cheat sheet":"Linux","powershell cheat sheet":"Windows Server",
    "cisco cheat sheet":"Cisco / Networking","subnet cheat sheet":"Subnetting",
    "ultimatesubnet cheat sheet":"Subnetting",
    "linux_windows_system_security":"Linux","linux_windows_application_services":"Linux",
    "directory_services_part1":"Windows Server","windows_ad_directory_services":"Windows Server",
    "windows_group_policies":"Windows Server","windows_security_pki":"Windows Server",
    "vpn_windows_linux":"Windows Server","linux_storage_lvm_raid":"Linux",
    "linux_mail_services":"Linux","intervlan_routing_ipv6":"Cisco / Networking",
    "routing_rip_ospf":"Cisco / Networking","subnetting_ospf_intervlan":"Subnetting",
    "cisco_ipv4_subnetting_vlsm":"Subnetting","cisco_ipv4_vlsm_ipv6":"Subnetting",
    "ospf_acl_dynamic_routing":"Cisco / Networking","acl_nat_pat":"Cisco / Networking",
}

CATEGORY_RULES = [
    (["subnet","subnetting","cidr","vlsm","binary","ultimatesubnet"],"Subnetting"),
    (["cisco","vlan","ospf","acl","nat","intervlan","datalink","transport","udp","tcp",
      "troubleshooting","networking_intro","routing_rip","ospf_acl","subnetting_ospf","acl_nat"],"Cisco / Networking"),
    (["windows","active directory","aduc","adds","powershell","delegation","sysprep","ou",
      "organizational","organisational","quick reference","important paths","dhcp","dc1","core",
      "round robin","directory_services","group_policies","security_pki","pki","gpo","rras",
      "sstp","pptp","nps","windows_ad","windows_group","windows_security","vpn_windows",
      "domain controller","active directory"],"Windows Server"),
    (["linux","dnf","rpm","bash","redhat","rocky","bind","named","zone","resolv","storage",
      "lvm","raid","mail","postfix","dovecot","openvpn","selinux","samba","apache","vpn",
      "intervlan_routing_ipv6"],"Linux"),
]

def infer_category(source, section):
    if source.lower() in SOURCE_CATEGORY_OVERRIDES:
        return SOURCE_CATEGORY_OVERRIDES[source.lower()]
    blob = (source + " " + section).lower()
    for keywords, label in CATEGORY_RULES:
        if any(k in blob for k in keywords): return label
    return "General"

def _source_to_display(source: str) -> str:
    KEEP_UPPER = {"CIDR","VLSM","DNS","DHCP","SSH","ACL","NAT","OSPF","RIP","AD","ADDS",
                  "ADUC","ADAC","GUI","CLI","OU","RFC","VM","VMs","DNF","RPM","SYSVOL",
                  "OOBE","APIPA","IP","TCP","UDP","PKI","GPO","NPS","PPTP","SSTP","LVM",
                  "RAID","VPN","IIS","FTP","SMB","TLS","CA","RAS","RRAS","DC","DC1","SRV",
                  "PC","SMTP","IMAP","POP3","MTA","MUA","MX"}
    CAT_PREFIXES = ("cisco_","linux_","windows_","subnet_")
    s = source.lower()
    for pfx in CAT_PREFIXES:
        if s.startswith(pfx):
            remainder = s[len(pfx):].replace("_cheat_sheet","").replace("cheat_sheet","") \
                                    .replace("_cheat","").replace("_sheet","").strip("_")
            if len(remainder) >= 3: s = s[len(pfx):]
            break
    s = re.sub(r"[_]?cheat[_]sheet$","",s)
    s = re.sub(r"[_]?cheat$","",s)
    s = re.sub(r"[_]?sheet$","",s)
    s = s.strip("_")
    if not s or len(s) < 3:
        s = re.sub(r"[_]?cheat[_]?sheet","",source.lower()).strip("_")
    s = s.replace("_"," ").replace("-"," ").strip()
    words = s.split()
    out = " ".join(w.upper() if w.upper() in KEEP_UPPER else w.title() for w in words)
    return out.encode("ascii",errors="ignore").decode("ascii").strip()[:55]

# Explicit query overrides for sources whose name doesn't make a good search query
# SOURCE_QUERY_OVERRIDES
# Maps source name → the search query run when user picks this topic from the browse menu.
# Rules for a good override query:
#   - Use 2-4 words that appear IN the actual content/section/tags of those entries
#   - Prefer broad terms that match multiple entries (the topic should show several results)
#   - For "cheat sheet" sources: target the most-searched content, not the source name
#   - For JSON sources: target a key section heading or unique term from the file
SOURCE_QUERY_OVERRIDES: dict = {
    # ── Subnetting ────────────────────────────────────────────────────────────
    "ultimatesubnet_cheat_sheet":       "subnet block size hosts",
    "subnet_cheat_sheet":               "subnet cidr mask prefix",
    "subnetting_ospf_intervlan":        "subnet ospf vlan",
    # ── Cisco ─────────────────────────────────────────────────────────────────
    "cisco_cheat_sheet":                "cisco router switch commands",
    "cisco_commands":                   "cisco show configure interface",
    "cisco_steps":                      "cisco vlan trunk configure",
    "acl_nat_pat":                      "cisco acl nat overload",
    "ospf_acl_dynamic_routing":         "cisco ospf passive interface",
    "routing_rip_ospf":                 "cisco rip ospf static route",
    "intervlan_routing_ipv6":           "cisco vlan trunk intervlan routing",
    # ── Windows Server ────────────────────────────────────────────────────────
    "user_cheat_sheet":                 "windows linux user group domain",
    "directory_services_part1":         "active directory domain controller promote",
    "windows_ad_directory_services":    "active directory domain controller create",
    "windows_group_policies":           "windows group policy gpo baseline",
    "windows_security_pki":             "windows pki certificate authority adcs",
    "vpn_windows_linux":                "vpn pptp sstp openvpn wireguard",
    # ── Linux ─────────────────────────────────────────────────────────────────
    "linux_mail_services":              "linux postfix dovecot smtp imap",
    "linux_storage_lvm_raid":           "linux lvm raid disk storage",
    # ── Catch-all for any powershell / windows core source names ─────────────
    # (add new sources here when you create new JSON files)
}

# Per-source FALLBACK queries used when a source is NOT in overrides AND
# the heading-word extraction produces something too specific (< 3 good words).
# Key = first meaningful word of the source name, value = prefix to prepend.
SOURCE_ANCHOR_WORDS: dict = {
    "powershell":   "windows powershell",
    "sconfig":      "windows server core sconfig",
    "windows":      "windows server",
    "linux":        "linux",
    "cisco":        "cisco",
    "subnet":       "subnet",
    "routing":      "cisco routing",
    "acl":          "cisco acl",
    "ospf":         "cisco ospf",
    "vpn":          "vpn",
    "mail":         "linux mail",
    "lvm":          "linux lvm",
    "raid":         "linux raid",
    "ad":           "active directory",
    "directory":    "active directory",
}


def _make_topic_query(source: str, src_rows: list, category: str) -> str:
    """
    Build a search query for a topic entry in topics.json.
    Strategy (in order of preference):
      1. Explicit override from SOURCE_QUERY_OVERRIDES
      2. Most-repeated section name + anchor word  (broad, hits many entries)
      3. SOURCE_ANCHOR_WORDS prefix + most common heading words
      4. Source name words + category anchor
    """
    src_lower = source.lower()

    # 1. Explicit override
    if src_lower in SOURCE_QUERY_OVERRIDES:
        return SOURCE_QUERY_OVERRIDES[src_lower]

    anchor = {"Linux":"linux","Windows Server":"windows","Cisco / Networking":"cisco",
              "Subnetting":"subnet","General":""}.get(category,"")

    query_stop = {
        "the","and","for","with","gui","all","important","quick","misc",
        "using","tools","commands","management","reference","overview",
        "introduction","basics","general","information","notes","from",
        "slides","section","part","lab","cheat","sheet","ultimate","getting",
        "help","discovering","interactive","menu","setup","tool","sconfig",
    }

    # 2. Find the most-repeated TOP-LEVEL section (not subsection).
    #    The most common section = the broadest representative topic.
    from collections import Counter
    section_counts = Counter(r.get("section","") for r in src_rows)
    top_sections = [s for s, _ in section_counts.most_common(3) if s]

    section_words = []
    seen_sw = set()
    for sec in top_sections:
        for w in re.findall(r"[a-zA-Z][a-zA-Z0-9]{2,}", sec):
            wl = w.lower()
            if wl not in query_stop and wl not in seen_sw:
                seen_sw.add(wl)
                section_words.append(wl)

    # 3. Check SOURCE_ANCHOR_WORDS for a prefix to prepend
    prefix_words = []
    for key, prefix in SOURCE_ANCHOR_WORDS.items():
        if key in src_lower:
            prefix_words = prefix.split()
            break

    # Merge: prefix first, then section words, deduplicated
    seen_final = set()
    final_words = []
    for w in prefix_words + section_words:
        if w not in seen_final:
            seen_final.add(w)
            final_words.append(w)

    # Add category anchor if not already covered
    if anchor and anchor not in seen_final:
        final_words.insert(0, anchor)

    if len(final_words) >= 2:
        return " ".join(final_words[:4])

    # 4. Last resort: source name words
    fallback = [w for w in source.replace("_"," ").replace("-"," ").split()
                if len(w)>=3 and w.lower() not in query_stop]
    if anchor and anchor not in fallback:
        fallback.insert(0, anchor)
    return " ".join(fallback[:4])


def generate_topics(rows: list, out_path: Path):
    import json
    from collections import OrderedDict
    BROWSE_EXCLUDE = {"scripts","scripts pretty","scripts_pretty"}
    seen_sources = OrderedDict()
    for row in rows:
        seen_sources.setdefault(row["source"], []).append(row)
    topics = []
    for source, src_rows in seen_sources.items():
        if source.lower() in BROWSE_EXCLUDE: continue
        all_sec = " ".join(r["section"]+" "+r["subsection"] for r in src_rows[:10])
        category = infer_category(source, all_sec)
        query   = _make_topic_query(source, src_rows, category)
        topics.append({"category":category,"display":_source_to_display(source),
                        "query":query,"source":source,"section":""})
    grouped = OrderedDict()
    for t in topics: grouped.setdefault(t["category"],[]).append(t)
    output = {"categories":[{"name":c,"topics":ts} for c,ts in grouped.items()]}
    with open(out_path,"w",encoding="utf-8") as fh:
        json.dump(output,fh,indent=2,ensure_ascii=False)
    total = sum(len(c["topics"]) for c in output["categories"])
    print(f"  topics.json  —  {total} topics in {len(output['categories'])} categories")
    return total


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
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

    txt_folder = Path(args.txt)
    txt_files  = sorted(txt_folder.glob("*.txt")) if txt_folder.exists() else []
    if txt_files:
        print(f"\nParsing .txt files from {txt_folder.resolve()}/\n")
        for fp in txt_files:
            rows = parse_file(fp)
            all_rows.extend(rows)
            print(f"  {fp.name:45s}  {len(rows):3d} entries")
    elif txt_folder.exists():
        print(f"\n  [txt] No .txt files in {txt_folder.resolve()}/  — skipped")
    else:
        print(f"\n  [txt] Folder not found: {txt_folder.resolve()}/  — skipped")

    json_folder = Path(args.json)
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

    print(f"\nPost-processing {len(all_rows)} entries...")

    # ── N-gram bonus tags (sklearn, corpus-wide) ───────────────────────────
    all_rows = inject_ngram_tags(all_rows)

    # ── TF-IDF + quality weights ───────────────────────────────────────────
    all_rows = compute_weights(all_rows)

    # ── Write CSV ──────────────────────────────────────────────────────────
    out_path = Path(args.out)
    fieldnames = ["source","section","subsection","type","content","tags","weight"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    note = "with nltk+sklearn" if (NLP_AVAILABLE and SKLEARN_AVAILABLE) \
           else "with nltk" if NLP_AVAILABLE \
           else "with sklearn" if SKLEARN_AVAILABLE \
           else "without NLP (install nltk + scikit-learn for best results)"
    print(f"\n[OK] {len(all_rows)} entries written {note}")
    print(f"     {out_path.resolve()}")

    topics_path = Path(args.topics)
    generate_topics(all_rows, topics_path)
    print(f"     {topics_path.resolve()}\n")
    print("Distribute to other PCs:")
    print("  knowledge_base.csv  +  topics.json  +  search_kb.ps1  +  kb.bat\n")


if __name__ == "__main__":
    main()