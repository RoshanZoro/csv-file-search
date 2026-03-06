# 🗂️ KB — Networking & Systems Knowledge Base

A personal, searchable knowledge base for **Cisco networking**, **Windows Server / Active Directory**, **Linux administration**, and **subnetting** — built from course lab documents and cheat sheets.

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
knowledge_base.csv     # Generated — all entries in one searchable flat file
topics.json            # Generated — browse menu for the PowerShell search tool
txt_to_kb_v9.py        # Build script: converts txt/ and json/ → knowledge_base.csv
add_tags_to_json.py    # Utility: auto-injects search tags into all json/ files
search_kb.ps1          # PowerShell search UI (run on any Windows PC, no Python needed)
kb.bat                 # One-click launcher for search_kb.ps1
```

---

## Quick start

### 1 — Build the knowledge base

```bash
# Install dependencies (one time)
pip install nltk rapidfuzz

# Generate knowledge_base.csv and topics.json from all source files
python txt_to_kb_v9.py
```

### 2 — Search (Windows, no Python needed)

Copy these four files to any PC and double-click `kb.bat`:

```
knowledge_base.csv   topics.json   search_kb.ps1   kb.bat
```

### 3 — Add a new topic

1. Convert your document to JSON using the schema below
2. Drop the `.json` file into `json/`
3. Run `python add_tags_to_json.py` to generate search tags
4. Run `python txt_to_kb_v9.py` to rebuild the CSV

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

> **Tip:** Leave out the `tags` field — `add_tags_to_json.py` generates it automatically.

---

## Tag generation

Tags are injected automatically by `add_tags_to_json.py` using:

- **Source keywords** — each known source has a seed word list (e.g. all Windows AD files get `active directory`, `domain controller`, `dc`, `adds`, `promote`, etc.)
- **Section keywords** — section/subsection text is matched against a keyword map to pull in related synonyms
- **Synonym expansion** — each matched word pulls in a synonym chain (e.g. `promote` → `domain controller, adds, forest, active directory`)
- **Content extraction** — significant words from the entry content itself, with stemming/lemmatisation if `nltk` is available

```bash
# Add tags to all json/ files (skips entries that already have tags)
python add_tags_to_json.py

# Preview without writing
python add_tags_to_json.py --dry-run

# Re-generate all tags (overwrite existing)
python add_tags_to_json.py --force

# Create .bak backups before modifying
python add_tags_to_json.py --backup
```

---

## Search tips

The PowerShell search tool matches against `section`, `subsection`, `content`, and `tags` simultaneously, so you can query naturally:

| Query | Finds |
|---|---|
| `create active directory` | AD DS install, domain controller promotion steps |
| `vpn certificate` | SSTP setup, PKI enrollment, RRAS cert binding |
| `ospf passive` | OSPF passive interface config on Cisco routers |
| `postfix tls` | Postfix TLS configuration, cert generation, Dovecot SSL |
| `nat overload` | PAT / ip nat inside source list ... overload |
| `vlsm` | VLSM subnetting examples and worked solutions |

---

## Sources

- Directory Services (Windows + VyOS + Linux lab)
- Inter-VLAN Routing & IPv6
- Subnetting & OSPF
- Windows Group Policies
- Routing (RIP & OSPF)
- Windows Security & PKI
- OSPF & ACL Dynamic Routing
- VPN under Windows & Linux
- Linux Mail Services (Postfix + Dovecot)
- ACL, NAT & PAT

---

## Requirements

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.8+ | Building the CSV |
| nltk | latest | Richer tag stemming (optional but recommended) |
| rapidfuzz | latest | Fuzzy search (optional) |
| PowerShell | 5.1+ | Running the search UI on Windows |

```bash
pip install nltk rapidfuzz
```

---

*Generated entries are filtered — submission requirements, screenshots, and sign-off criteria are automatically stripped and won't appear in search results.*
