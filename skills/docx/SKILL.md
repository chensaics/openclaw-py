---
skill_key: docx
description: Read and extract text from Microsoft Word files.
version: 1.0.0
emoji: 📝
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: standard
deps: py:docx
userInvocable: true
disableModelInvocation: false
capability: office-reader, docx-extraction
install: pip install "openclaw-py[office]"
healthcheck: python -c "import docx; print('ok')"
rollback: Fall back to plain text attachment flow when DOCX parsing is unavailable.
---

# DOCX Reader

Read and extract text from Microsoft Word (.docx) files.

## Available Tools

- **read_docx** — Extract paragraphs and tables from a Word document

## Usage

> "Read the file proposal.docx"
> "Summarize the contents of meeting-notes.docx"
