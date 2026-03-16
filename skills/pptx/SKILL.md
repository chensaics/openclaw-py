---
skill_key: pptx
description: Read and extract text from PowerPoint presentations.
version: 1.0.0
emoji: 📽️
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: standard
deps: py:pptx
userInvocable: true
disableModelInvocation: false
capability: office-reader, pptx-extraction
install: pip install "openclaw-py[office]"
healthcheck: python -c "import pptx; print('ok')"
rollback: Fall back to static slide notes/manual extraction flow.
---

# PPTX Reader

Read and extract text from PowerPoint (.pptx) presentations.

## Available Tools

- **read_pptx** — Extract slide text and notes from a presentation

## Usage

> "Read the presentation pitch-deck.pptx"
> "Summarize all slides in quarterly-review.pptx"
