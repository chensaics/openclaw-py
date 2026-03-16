---
skill_key: xlsx
description: Read and extract data from Excel spreadsheets.
version: 1.0.0
emoji: 📊
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: standard
deps: py:openpyxl
userInvocable: true
disableModelInvocation: false
capability: office-reader, xlsx-extraction
install: pip install "openclaw-py[office]"
healthcheck: python -c "import openpyxl; print('ok')"
rollback: Fall back to CSV export/import route when XLSX parsing is unavailable.
---

# XLSX Reader

Read and extract data from Excel (.xlsx) spreadsheets.

## Available Tools

- **read_xlsx** — Read a spreadsheet, optionally targeting a specific sheet

## Usage

> "Read the spreadsheet budget.xlsx"
> "Show data from the 'Q1' sheet in sales.xlsx"
