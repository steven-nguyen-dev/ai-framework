---
name: lotteon-api-extractor
description: Automatically extracts, parses, translates, and generates OpenAPI 3.0.3 specifications and raw JSON metadata from LotteON API Center.
disable-model-invocation: true
version: 0.0.1
---

# LotteON API Extractor Skill

Use this skill whenever the user requests extracting, scraping, translating, or generating OpenAPI specifications for **LotteON API Center** (`https://api.lotteon.com/apiService`).

---

## 🛑 MANDATORY PRE-CHECK: TARGET URL REQUIRED

> [!IMPORTANT]
> If invoked without a target URL argument, default to `https://api.lotteon.com/apiService`.

---

## 🏗️ Architecture & Features

This skill is powered by the self-contained **LotteON Extraction Engine** (`scripts/lotteon_extractor.py`):

1. **Nuxt REST Endpoint Discovery**: Communicates directly with LotteON's backend service at `https://soapi.lotteon.com` to fetch all 193 API definitions across 12 modules.
2. **Pixel-Indentation Stack Engine**: Parses CSS `margin-left` pixel offsets (`0px`, `15px`, `30px`, `45px`, `60px`) to construct 1-to-1 matching nested object/array schemas (`data` → `itmLst` → `clrchipLst`). Places price (`slPrc`) and stock (`stkQty`) at variant level (`itmLst`).
3. **Common-Code Enum Harvester**: Extracts 318+ common-code enum tables (`SL_STAT_CD`, `PD_TYP_CD`, `DV_CO_CD`, `MALL_DVS_CD`) directly from documentation HTML and attaches `enum` arrays and English descriptions.
4. **OpenAPI 3.0.3 Compliance**: Outputs standard `requestBody` objects for `POST`/`PUT`/`PATCH`, adds HTTP failure contracts (`401`, `403`, `404`, `429`, `500`), clarifies `dataCount` pagination and 1-based `pageNo` index, and adds `ApiKeyAuth` security schemes.
5. **Schema-Example Alignment**: Attaches realistic multi-variant payload examples (`example` keys) aligned 100% with schemas.
6. **Machine Translation**: Automatically translates all Korean field descriptions, titles, and tags into English via concurrent neural translation.

---

## 🚀 Quick Start / Usage

Run the production extraction script from terminal:

```bash
python3 scripts/lotteon_extractor.py --url https://api.lotteon.com/apiService --output-dir ./api-docs
```

### Options:
- `--url`: Target API portal URL (default: `https://api.lotteon.com/apiService`).
- `--output-dir`: Output directory path (default: `./api-docs`).

---

## 📄 Output Deliverables

The script produces two primary deliverables in the specified output directory:

1. 📄 **`lotteon_openapi_v3_english.json`**: Complete, validated **OpenAPI 3.0.3 Specification** in English, ready to import into Postman, Insomnia, Swagger UI, or SDK generators.
2. 📄 **`lotteon_raw_api_data.json`**: Complete raw JSON metadata backup extracted from LotteON.
