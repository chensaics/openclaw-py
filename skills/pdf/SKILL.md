---
skill_key: pdf
description: Read and extract text from PDF files.
version: 1.0.0
emoji: 📄
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: standard
deps: py:pypdf
userInvocable: true
disableModelInvocation: false
capability: office-reader, pdf-extraction
install: pip install "openclaw-py[office]"
healthcheck: python -c "import pypdf; print('ok')"
rollback: Fall back to plain text attachment flow when PDF parsing is unavailable.
---

# PDF Reader

Read and extract text from PDF files.

## Available Tools

- **read_pdf** — Extract text from a PDF file, optionally specifying page range

## Usage

> "Read the file report.pdf and summarize it"
> "Extract pages 5-10 from document.pdf"
