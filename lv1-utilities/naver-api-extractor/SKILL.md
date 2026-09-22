---
name: naver-api-extractor
description: Automatically extracts, parses, translates, and generates OpenAPI 3.0.3 specifications and raw JSON metadata for Naver Commerce and Developers API Platform.
disable-model-invocation: true
version: 0.0.1
---

# Naver API Extractor Skill

Use this skill whenever the user requests extracting, scraping, translating, or generating OpenAPI specifications for **Naver Commerce API Center** (`https://apicenter.commerce.naver.com`) or **Naver Developers API** (`https://developers.naver.com`).

---

## 🛑 MANDATORY PRE-CHECK: TARGET URL REQUIRED

> [!IMPORTANT]
> If invoked without a target URL argument, default to `https://apicenter.commerce.naver.com`.

---

## 🏗️ Architecture & Features

This skill is powered by the self-contained **Naver Extraction Engine** (`scripts/naver_extractor.py`):

1. **Naver API Catalog Crawling**: Fetches all Naver OpenAPIs across Shopping, Commerce, Search, DataLab, Papago Translation, and User Authentication.
2. **Table Schema Parsing**: Extracts query parameters, POST request body properties, and response payload properties directly from HTML parameter tables.
3. **OpenAPI 3.0.3 Security Schemes**: Configures Naver header authentication schemes (`X-Naver-Client-Id` and `X-Naver-Client-Secret`).
4. **Failure Contracts**: Adds HTTP failure responses (`400`, `401`, `403`, `404`, `500`) to all endpoints.
5. **Machine Translation**: Automatically translates all Korean titles, field descriptions, and category tags into English via concurrent neural translation.

---

## 🚀 Quick Start / Usage

Run the production extraction script from terminal:

```bash
python3 scripts/naver_extractor.py --url https://apicenter.commerce.naver.com --output-dir ./api-docs
```

### Options:
- `--url`: Target API portal URL (default: `https://apicenter.commerce.naver.com`).
- `--output-dir`: Output directory path (default: `./api-docs`).

---

## 📄 Output Deliverables

The script produces two primary deliverables in the specified output directory:

1. 📄 **`naver_openapi_v3_english.json`**: Complete, validated **OpenAPI 3.0.3 Specification** in English, ready to import into Postman, Insomnia, Swagger UI, or SDK generators.
2. 📄 **`naver_raw_api_data.json`**: Complete raw JSON metadata backup extracted from Naver.
