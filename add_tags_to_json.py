"""
add_tags_to_json.py
====================
Reads all .json files in your json/ folder and injects a "tags" field
into every entry using the same tag engine as txt_to_kb_v9.py.

Run this ONCE after converting new documents, or whenever you want to
refresh tags after editing SOURCE_KEYWORDS / SYNONYMS / SECTION_KEYWORDS.

Usage:
    python add_tags_to_json.py                      # processes json/ folder
    python add_tags_to_json.py --folder path/to/json
    python add_tags_to_json.py --backup             # saves .bak before overwriting
    python add_tags_to_json.py --dry-run            # preview without writing

Options:
    --folder     Folder containing .json files (default: ./json)
    --backup     Save a .bak copy of each file before modifying
    --dry-run    Print what would change without writing anything
    --force      Re-generate tags even if entry already has a "tags" field
"""

import re, json, shutil, argparse
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
#  TAG ENGINE  (copy-paste from txt_to_kb_v9.py — keep in sync)
# ══════════════════════════════════════════════════════════════════════════════

try:
    import nltk
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    from nltk.corpus import stopwords as nltk_stopwords
    for _pkg in ("wordnet", "omw-1.4", "stopwords"):
        try:
            nltk.data.find(f"corpora/{_pkg}")
        except LookupError:
            nltk.download(_pkg, quiet=True)
    _stemmer    = PorterStemmer()
    _lemmatizer = WordNetLemmatizer()
    _nltk_stop  = set(nltk_stopwords.words("english"))
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False
    _stemmer = _lemmatizer = _nltk_stop = None

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
    "rip":                     ["cisco","rip","routing","dynamic","distance vector","update","version","redistribute"],
    "intervlan":               ["cisco","intervlan","vlan","routing","subinterface","dot1q","encapsulation","router","stick"],
    "the basics":              ["subnet","subnetting","basics","ipv4","network","host","mask","portion","split"],
    "slash notation":          ["subnet","cidr","slash","notation","prefix","bits","ones","zeros"],
    "special addresses":       ["subnet","special","network","broadcast","usable","first","last","formula"],
    "formula":                 ["subnet","formula","block","size","calculate","usable","hosts","256"],
    "reference table":         ["subnet","reference","table","hosts","block","size","subnets","cidr"],
    "vlsm":                    ["subnet","vlsm","variable","length","efficient","assign","allocate","largest","first","steps"],
    "private ip":              ["subnet","private","ip","rfc","1918","range","internal","class","not","routable"],
    "binary":                  ["subnet","binary","decimal","convert","bits","octet","position","value","hex"],
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
    "group":            ["groups","groupadd","groupmod","groupdel","member","membership"],
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

_CATEGORY_SEED_KEYWORDS = {
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


def _register_source(source: str, category: str):
    if source not in SOURCE_KEYWORDS:
        seeds = list(_CATEGORY_SEED_KEYWORDS.get(category, []))
        for w in re.findall(r"[a-z]{3,}", source.replace("_", " ")):
            if w not in seeds:
                seeds.append(w)
        SOURCE_KEYWORDS[source] = seeds


def make_tags(source: str, section: str, subsection: str, content: str) -> list:
    """Returns a list of tag strings (not comma-joined — stored as JSON array)."""
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
                        seen.add(syn)
                        tags.append(syn)

    for kw in SOURCE_KEYWORDS.get(source, []):
        add(kw)

    blob_sec = (section + " " + subsection).lower()
    for key, words in SECTION_KEYWORDS.items():
        if key in blob_sec:
            for w in words: add(w)

    all_text = f"{section} {subsection} {content}".lower()
    for w in re.findall(r"[a-z][a-z0-9\-]{1,}", all_text):
        if _is_stop(w): continue
        add(w, _stem(w), _lemma(w))
        for pfx in ("user","group","net","fast","get","ip","no","show"):
            if w.startswith(pfx) and len(w) > len(pfx) + 2:
                add(w[len(pfx):])

    return tags[:150]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def process_file(filepath: Path, dry_run: bool, backup: bool, force: bool) -> dict:
    """
    Processes one JSON file. Returns a summary dict:
      { "file": name, "entries": total, "tagged": added/updated, "skipped": already had tags }
    """
    with open(filepath, encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as e:
            print(f"  [SKIP] {filepath.name} — JSON error: {e}")
            return {"file": filepath.name, "entries": 0, "tagged": 0, "skipped": 0, "error": str(e)}

    source   = data.get("source", filepath.stem)
    category = data.get("category", "General").strip()
    entries  = data.get("entries", [])

    _register_source(source, category)

    tagged = 0
    skipped = 0

    for entry in entries:
        section    = entry.get("section", "").strip()
        subsection = entry.get("subsection", "").strip()
        content    = entry.get("content", "").replace("\\n", "\n").strip()

        # Skip if already has tags and --force not set
        if "tags" in entry and not force:
            skipped += 1
            continue

        if not section or not content:
            skipped += 1
            continue

        tags = make_tags(source, section, subsection, content)

        # Insert "tags" after "type" (before "content") for clean ordering
        new_entry = {}
        for key in ("section", "subsection", "type"):
            if key in entry:
                new_entry[key] = entry[key]
        new_entry["tags"] = tags
        new_entry["content"] = entry.get("content", "")
        # Carry over any extra fields
        for key, val in entry.items():
            if key not in new_entry:
                new_entry[key] = val

        entry.clear()
        entry.update(new_entry)
        tagged += 1

    summary = {
        "file":    filepath.name,
        "entries": len(entries),
        "tagged":  tagged,
        "skipped": skipped,
    }

    if dry_run:
        return summary

    if tagged > 0:
        if backup:
            shutil.copy2(filepath, filepath.with_suffix(".json.bak"))

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    return summary


def main():
    ap = argparse.ArgumentParser(description="Inject tags into all JSON knowledge base files")
    ap.add_argument("--folder",  default="json", help="Folder with .json files (default: ./json)")
    ap.add_argument("--backup",  action="store_true", help="Save .bak before overwriting")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run", help="Preview without writing")
    ap.add_argument("--force",   action="store_true", help="Re-generate tags even if already present")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder.resolve()}")
        return

    json_files = [f for f in sorted(folder.glob("*.json"))
                  if not f.name.startswith("_") and f.name != "topics.json"]

    if not json_files:
        print(f"[INFO] No .json files found in {folder.resolve()}")
        return

    mode = "DRY RUN — " if args.dry_run else ""
    print(f"\n{mode}Processing {len(json_files)} file(s) in {folder.resolve()}/\n")
    if args.backup and not args.dry_run:
        print("  Backup mode ON — .bak files will be created\n")

    total_entries = total_tagged = total_skipped = 0

    for fp in json_files:
        result = process_file(fp, dry_run=args.dry_run, backup=args.backup, force=args.force)
        status = "DRY" if args.dry_run else ("OK " if result["tagged"] > 0 else "---")
        print(f"  [{status}] {result['file']:45s}  "
              f"{result['tagged']:3d} tagged  /  "
              f"{result['skipped']:3d} skipped  /  "
              f"{result['entries']:3d} total")
        total_entries += result["entries"]
        total_tagged  += result["tagged"]
        total_skipped += result["skipped"]

    print(f"\n{'(dry run) ' if args.dry_run else ''}Done: "
          f"{total_tagged} entries tagged, "
          f"{total_skipped} skipped (already had tags), "
          f"{total_entries} total across {len(json_files)} files\n")

    if not args.dry_run and total_tagged > 0:
        print("Re-run txt_to_kb_v9.py to regenerate knowledge_base.csv with the new tags.\n")


if __name__ == "__main__":
    main()