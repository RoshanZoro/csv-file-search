# 🗂️ KB — Networking & Systems Knowledge Base

A personal, searchable knowledge base for **Cisco networking**, **Windows Server / Active Directory**, **Linux administration**, and **subnetting** — built from lab documents and cheat sheets.

---

## What's in here

| Category | Topics covered |
|---|---|
| 🔵 **Cisco / Networking** | VLANs, trunking, OSPF, RIP, ACLs, NAT/PAT, inter-VLAN routing, IPv6 |
| 🟣 **Windows Server** | Active Directory, Group Policy, PKI/ADCS, VPN (PPTP/SSTP), RRAS, NPS |
| 🟢 **Linux** | Postfix/Dovecot mail, OpenVPN, LVM/RAID, DNS (BIND), SELinux, storage |
| 🟡 **Subnetting** | CIDR, VLSM, binary conversion, subnet tables, worked examples |

---

## Files

```
txt/                   # Raw .txt cheat sheets and lab notes
json/                  # Structured knowledge entries (one file per topic)
knowledge_base.csv     # Generated — all entries with tags and TF-IDF weights
topics.json            # Generated — browse menu for the PowerShell search tool
main.py                # Build script: converts txt/ and json/ → knowledge_base.csv
search_kb.ps1          # PowerShell search UI (run on any Windows PC, no Python needed)
kb.bat                 # One-click launcher for search_kb.ps1
```

---

## Quick start

### 1 — Build the knowledge base

```bash
# Install dependencies (one time)
pip install nltk scikit-learn rapidfuzz

# Generate knowledge_base.csv and topics.json from all source files
python main.py
```

### 2 — Search (Windows, no Python needed)

Copy these four files to any PC and double-click `kb.bat`:

```
knowledge_base.csv   topics.json   search_kb.ps1   kb.bat
```

### 3 — Add a new topic

1. Convert your document to JSON using the schema below
2. Drop the `.json` file into `json/`
3. Run `python main.py` to rebuild the CSV

---

## JSON schema

Each file in `json/` follows this structure:

```json
{
  "source": "my_topic_name",
  "category": "Linux | Windows Server | Cisco / Networking | Subnetting",
  "entries": [
    {
      "section": "SECTION HEADING IN CAPS",
      "subsection": "Sub-heading (or empty string)",
      "type": "command | steps | prose",
      "content": "line one\nline two\nline three"
    }
  ]
}
```

**Field rules:**

| Field | Notes |
|---|---|
| `source` | Lowercase, underscores, no spaces — e.g. `linux_bind_dns` |
| `category` | Used for browse grouping and tag seeding |
| `section` | ALL CAPS — top-level heading |
| `subsection` | Title Case — sub-heading, or `""` if none |
| `type` | `command` for CLI/config, `steps` for numbered instructions, `prose` for explanations |
| `content` | Use `\n` for line breaks. Preserve commands exactly as written |

> **Tip:** Leave out the `tags` field — `main.py` generates it automatically.

---

## How the build works

`main.py` processes all source files and outputs a CSV with the following columns:

| Column | Description |
|---|---|
| `source` | Origin file name |
| `section` | Top-level heading |
| `subsection` | Sub-heading |
| `type` | `command`, `steps`, or `prose` |
| `content` | Full entry text |
| `tags` | Auto-generated search tags |
| `weight` | TF-IDF quality score (0.0 – 1.0) |

### Tag generation

Tags are injected automatically using:

- **Source keywords** — each known source has a seed word list (e.g. all Windows AD files get `active directory`, `domain controller`, `dc`, `adds`, `promote`, etc.)
- **Section keywords** — section/subsection text is matched against a keyword map to pull in related synonyms
- **Synonym expansion** — each matched word pulls in a synonym chain (e.g. `promote` → `domain controller, adds, forest, active directory`)
- **N-gram extraction** — sklearn TF-IDF extracts the most distinctive 2–3 word phrases per entry (e.g. `ip helper-address`, `easy-rsa pki`, `passive-interface default`) and appends them as bonus tags
- **Co-occurrence tags** — when two related terms appear in the same entry, a compound tag is injected (e.g. content with both `ospf` and `passive` gets the tag `ospf passive`)
- **Content extraction** — significant words from the entry content itself, with stemming/lemmatisation if `nltk` is available

### TF-IDF weight

Each entry receives a `weight` float baked into the CSV. Entries about rare, specific topics score higher than generic ones. The PowerShell search multiplies the raw match score by this weight, so `restorecon` beats `windows configure` in ranking even if both contain your search term.

---

## Search tips

The PowerShell search tool matches against `section`, `subsection`, `content`, and `tags` simultaneously. Natural language queries work:

| Query | Finds |
|---|---|
| `create active directory` | AD DS install, domain controller promotion steps |
| `add desktop to domain` | Steps to join a Windows client to the domain |
| `how many hosts in a /26` | Subnet host tables, CIDR reference |
| `vpn certificate` | SSTP setup, PKI enrollment, RRAS cert binding |
| `ospf passive interface` | OSPF passive interface config on Cisco routers |
| `postfix tls` | Postfix TLS configuration, cert generation, Dovecot SSL |
| `nat overload` | PAT / ip nat inside source list ... overload |
| `vlsm` | VLSM subnetting examples and worked solutions |

**Filters**

```powershell
.\search_kb.ps1 "vlan" -CommandOnly        # commands only
.\search_kb.ps1 "domain" -StepsOnly        # step-by-step guides only
.\search_kb.ps1 "ospf" -MaxResults 50      # show more results
.\search_kb.ps1 "ospf" -NoGroup            # flat list, no source grouping
```

**Fuzzy fallback** — typos are detected and flagged even when synonym matching still returns results:

```
Search: opsf
  Did you mean: 'opsf' → 'ospf'
```

---

## Requirements

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.8+ | Building the CSV |
| scikit-learn | latest | TF-IDF weights and n-gram tag extraction (optional) |
| nltk | latest | Richer tag stemming (optional) |
| rapidfuzz | latest | Fuzzy search (optional) |
| PowerShell | 5.1+ | Running the search UI on Windows |

```bash
pip install nltk scikit-learn rapidfuzz
```

The CSV and PowerShell search script are fully standalone — once the CSV is built, Python is not needed on the target machine.
