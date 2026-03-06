# KB — Offline Knowledge Base Search

A portable, offline-first knowledge base for sysadmin cheat sheets. Search commands, steps, and reference material from a Windows command prompt — no internet, no browser, no extra software needed on the machines you use it on.

---

## How it works

You write or paste your notes as `.txt` or `.json` files and run a Python script **once** on your own machine to generate a CSV database. That database, along with two small scripts, is everything you need. Copy those three files to any Windows PC and search instantly.

```
[Your notes]  →  python txt_to_kb.py  →  knowledge_base.csv
                                       →  topics.json
                          +  search_kb.ps1
                          +  kb.bat
                          └─ Copy these 4 files anywhere → works offline
```

---

## Repository structure

```
kb/
├── txt/                        ← Paste .txt cheat sheets here
│   ├── user_cheat_sheet.txt
│   ├── cisco_cheat_sheet.txt
│   └── ...
│
├── json/                       ← Write structured .json entries here
│   └── _template.json          ← Copy this as a starting point (ignored by parser)
│
├── txt_to_kb.py                ← Run once at home to generate the database
│
├── knowledge_base.csv          ← Generated — copy to all PCs
├── topics.json                 ← Generated — copy to all PCs
├── search_kb.ps1               ← Copy to all PCs
├── kb.bat                      ← Copy to all PCs
│
└── kb_json_prompt.txt          ← Claude prompt to convert notes to JSON format
```

---

## Getting started

### 1. Generate the database (run once, on your own PC)

Install dependencies:

```bash
pip install nltk rapidfuzz
```

> `nltk` and `rapidfuzz` are optional but improve tag quality. The script works without them.

Run the parser:

```bash
python txt_to_kb.py
```

This reads all `.txt` files from `txt/` and all `.json` files from `json/`, and outputs:
- `knowledge_base.csv` — the searchable database
- `topics.json` — the browse menu, auto-generated from your content

### 2. Deploy to any PC

Copy these 4 files to a folder on each machine (USB stick, network share, wherever):

```
knowledge_base.csv
topics.json
search_kb.ps1
kb.bat
```

No Python, no installs needed on those machines.

### 3. Run

Double-click `kb.bat` or run it from a command prompt.

---

## Usage

```
 ==============================================================
  KB  //  Knowledge Base Search
 ==============================================================

  [1]  Search
  [2]  Browse by topic
  [3]  Commands only  (quick lookup)
  [4]  Help
  [0]  Exit
```

**Search** — type any natural language query:
```
Search: how to create linux user
Search: join desktop to domain
Search: vlan trunk configuration
Search: vlsm example
```

**Browse by topic** — dynamically built from your content, grouped by category (Linux, Windows Server, Cisco / Networking, Subnetting).

**Commands only** — same as search but filters to `[COMMAND]` type entries only, useful for quick syntax lookups.

Result types are colour-coded:
- 🟢 `[COMMAND]` — CLI commands, config lines
- 🟣 `[STEPS]` — numbered GUI/procedure steps
- 🔵 `[PROSE]` — explanatory text, reference tables

---

## Adding new content

### Option A — Paste a cheat sheet as `.txt`

Drop any `.txt` file into the `txt/` folder. The parser auto-detects the format (underline-style headings, dash-divided sections, or flat numbered sections) and splits it into searchable entries.

Then re-run:
```bash
python txt_to_kb.py
```

### Option B — Write structured `.json`

Better for content you write yourself — no ambiguity, full control over how entries are split and labelled.

Copy `json/_template.json`, rename it (without the leading `_`), and fill it in:

```json
{
  "source": "my_topic",
  "category": "Linux",
  "entries": [
    {
      "section": "MY TOPIC: INSTALL SOMETHING",
      "subsection": "Install",
      "type": "command",
      "content": "sudo dnf install something   # Install the package\nsudo systemctl enable something"
    },
    {
      "section": "MY TOPIC: INSTALL SOMETHING",
      "subsection": "Verify",
      "type": "command",
      "content": "systemctl status something"
    }
  ]
}
```

**JSON fields:**

| Field | Required | Description |
|---|---|---|
| `source` | Yes | Short identifier, no spaces. Shown as `Source:` in results. |
| `category` | No | Browse menu category. Auto-detected if omitted. |
| `entries` | Yes | List of KB entries. Each becomes one search result. |
| `section` | Yes (per entry) | Top-level heading, ALL CAPS. Shared across related entries. |
| `subsection` | No | Sub-heading within the section. Use `""` to leave blank. |
| `type` | No | `command`, `steps`, or `prose`. Auto-detected if omitted. |
| `content` | Yes (per entry) | The content. Use `\n` for line breaks. |

Files starting with `_` are ignored by the parser (use for templates and drafts).

### Using the Claude prompt

`kb_json_prompt.txt` contains a prompt you can paste into Claude to automatically convert any cheat sheet or notes into the correct JSON format. Paste the prompt, then add your text at the bottom. Claude returns ready-to-use JSON.

---

## How search works

The search engine uses a **two-tier matching** system:

1. **Direct match** — the term appears literally in the section, subsection, or content text. Scored highest.
2. **Synonym fallback** — if a term isn't in the text, synonyms and related keywords are checked against the pre-expanded tag column. Used as a fallback only.

**Inclusion rule:** every query term must match somewhere, and at least half must be direct hits. This prevents over-broad synonym matches from flooding results with unrelated entries.

Scoring weights:
- Term in subsection: **+8**
- Term in section: **+4**
- Term in content: **+2**
- All terms present together in content: **+5 bonus**
- Entry is steps type: **+2**
- Entry is command type: **+1**

Common filler words (`how`, `to`, `the`, `a`, `in`, etc.) are stripped from queries automatically, so `how to create a linux user` and `create linux user` give the same results.

---

## Parser command-line options

```bash
# Default (reads txt/ and json/, writes to current folder)
python txt_to_kb.py

# Custom paths
python txt_to_kb.py --txt path/to/txt --json path/to/json --out kb.csv --topics topics.json
```

| Flag | Default | Description |
|---|---|---|
| `--txt` | `./txt` | Folder containing `.txt` source files |
| `--json` | `./json` | Folder containing `.json` source files |
| `--out` | `./knowledge_base.csv` | Output CSV path |
| `--topics` | `./topics.json` | Output topics JSON path |

---

## Category detection

The browse menu groups topics into categories automatically based on keywords in the source filename and section names:

| Category | Detected from |
|---|---|
| Subnetting | `subnet`, `cidr`, `vlsm`, `binary`, `ultimatesubnet` |
| Linux | `linux`, `dnf`, `rpm`, `bash`, `redhat`, `bind`, `named` |
| Cisco / Networking | `cisco`, `vlan`, `ospf`, `routing`, `acl`, `nat` |
| Windows Server | `windows`, `active directory`, `aduc`, `powershell`, `dns`, `dhcp`, `dc` |

To override the detected category for a JSON file, set the `category` field explicitly.

---

## Requirements

**To generate the database** (your machine only):
- Python 3.10+
- `pip install nltk rapidfuzz` *(optional, improves tag quality)*

**To use the search tool** (any Windows PC):
- Windows PowerShell (built into Windows, no install needed)
- The 4 files: `knowledge_base.csv`, `topics.json`, `search_kb.ps1`, `kb.bat`
