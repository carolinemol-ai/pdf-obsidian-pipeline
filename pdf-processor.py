#!/usr/bin/env python3
"""PDF processor: extract text, distill with Ollama, file to Obsidian."""

import sys
import os
import subprocess
import shutil
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"
VAULT = Path.home() / "Obsidian" / "Work Vault"
PROCESSED_LOG = Path.home() / ".claude" / "scripts" / "processed_pdfs.log"

# Routing table
# Knowledge base: external publications, research, transcripts by others
# Deliverables:   Caroline's own work products (proposals, decks, reports)
# Inbox:          Anything unclear
# Skip:           Invoices, CVs/resumes, receipts, forms — left in Downloads
# MD notes land in the category folder root; PDFs go in _PDFs/ subfolder
CATEGORIES = {
    "ai-higher-ed":  VAULT / "05-Knowledge-Base" / "AI-in-Higher-Ed",
    "learning-tech": VAULT / "05-Knowledge-Base" / "Learning-Technology",
    "deliverable":   VAULT / "02-Clients" / "_Deliverables",
    "inbox":         VAULT / "00-Inbox",
}
PDF_SUBFOLDERS = {
    "ai-higher-ed":  VAULT / "05-Knowledge-Base" / "AI-in-Higher-Ed" / "_PDFs",
    "learning-tech": VAULT / "05-Knowledge-Base" / "Learning-Technology" / "_PDFs",
    "deliverable":   VAULT / "02-Clients" / "_Deliverables" / "_PDFs",
    "inbox":         VAULT / "00-Inbox",
}


def notify(title: str, subtitle: str, body: str):
    script = (
        f'display notification {json.dumps(body)} '
        f'with title {json.dumps(title)} '
        f'subtitle {json.dumps(subtitle)}'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)


def extract_text(pdf_path: Path, max_chars: int = 6000) -> str:
    result = subprocess.run(
        ["pdftotext", "-l", "15", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout[:max_chars].strip()


def ollama_running() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def distill(text: str, filename: str) -> dict:
    prompt = f"""You are filing a PDF into a knowledge base for an AI strategy consultant in higher education. Classify and summarize this document.

Filename: {filename}
Text:
---
{text}
---

CLASSIFICATION RULES (apply in order):
1. skip=true: invoices, receipts, CVs/resumes, blank forms, contracts — leave in Downloads.
2. "deliverable": Caroline's OWN authored work. Signs: her name as author, "Prepared by Caroline Mol", "Prepared for [client]", confidential client documents, pitch decks she created, workshop materials she wrote. If the document appears to be created BY Caroline FOR a client, it is a deliverable.
3. "ai-higher-ed": external research/reports/papers on AI in higher education, academic AI policy, pedagogy with AI — written by OTHER people or organizations, not Caroline.
4. "learning-tech": external research on learning design, edtech, LMS, instructional design — written by others, not AI-specific.
5. "inbox": anything that doesn't clearly fit above.

For relevant_to, pick EXACTLY ONE: workshops, HEAIC, client work, or personal learning.

Return ONLY a valid JSON object, no markdown, no explanation:
{{
  "title": "clean document title",
  "category": "deliverable",
  "summary": "2-3 sentence summary",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "key_takeaway": "single most important insight, max 15 words",
  "notable_quote": "one direct quote, or empty string",
  "relevant_to": "client work",
  "tags": ["tag1", "tag2", "tag3"],
  "skip": false
}}"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1}
    }).encode()

    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return json.loads(result["response"])


def already_processed(pdf_path: Path) -> bool:
    if not PROCESSED_LOG.exists():
        return False
    return str(pdf_path) in PROCESSED_LOG.read_text()


def mark_processed(pdf_path: Path):
    PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_LOG, "a") as f:
        f.write(str(pdf_path) + "\n")


def build_note(data: dict, pdf_dest: Path, date: str) -> str:
    tags_yaml = "\n".join(f"  - {t}" for t in data.get("tags", []))
    insights = "\n".join(f"- {i}" for i in data.get("key_insights", []))
    quote = (
        f'\n## Notable Quote\n> {data["notable_quote"]}\n'
        if data.get("notable_quote") else ""
    )
    return f"""---
title: "{data['title']}"
date: {date}
source: "[[{pdf_dest.name}]]"
type: resource
tags:
{tags_yaml}
relevant_to: {data.get('relevant_to', '')}
---

## Summary
{data['summary']}

## Key Insights
{insights}

## Key Takeaway
**{data['key_takeaway']}**
{quote}"""


def safe_filename(title: str, max_len: int = 60) -> str:
    return "".join(c for c in title if c.isalnum() or c in " -_").strip()[:max_len]


def process(pdf_path: Path):
    if already_processed(pdf_path):
        return

    # Wait for file to finish writing
    time.sleep(3)

    if not pdf_path.exists():
        return

    if not ollama_running():
        notify("PDF Processor", "Ollama not running", "Start Ollama.app, then re-download the PDF")
        return

    try:
        text = extract_text(pdf_path)
        if not text:
            notify("PDF Skipped", pdf_path.name[:40], "Could not extract text — left in Downloads")
            mark_processed(pdf_path)
            return

        data = distill(text, pdf_path.name)

        if data.get("skip"):
            notify("PDF Skipped", data.get("title", pdf_path.name)[:40], "Invoice/CV/form — left in Downloads")
            mark_processed(pdf_path)
            return

        category = data.get("category", "inbox")
        dest_folder = CATEGORIES.get(category, CATEGORIES["inbox"])
        pdf_folder = PDF_SUBFOLDERS.get(category, dest_folder)
        dest_folder.mkdir(parents=True, exist_ok=True)
        pdf_folder.mkdir(parents=True, exist_ok=True)

        date = datetime.now().strftime("%Y-%m-%d")
        pdf_dest = pdf_folder / pdf_path.name
        note_path = dest_folder / f"{safe_filename(data['title'])}.md"

        shutil.move(str(pdf_path), str(pdf_dest))
        note_path.write_text(build_note(data, pdf_dest, date))
        mark_processed(pdf_path)

        labels = {
            "ai-higher-ed":  "Knowledge Base → AI/Higher Ed",
            "learning-tech":  "Knowledge Base → Learning Tech",
            "deliverable":    "Clients → Deliverables",
            "inbox":          "Inbox",
        }
        notify(
            f"Saved: {data['title'][:45]}",
            labels.get(category, category),
            data.get("key_takeaway", "Filed successfully")
        )

    except json.JSONDecodeError as e:
        notify("PDF Processor Error", pdf_path.name[:40], f"Parse error: {e}")
    except Exception as e:
        notify("PDF Processor Error", pdf_path.name[:40], str(e)[:100])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pdf-processor.py <path-to-pdf>")
        sys.exit(1)
    process(Path(sys.argv[1]))
