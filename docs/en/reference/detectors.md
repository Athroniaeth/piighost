---
icon: lucide/list
---

# Reference Pre-built detectors

Catalog of the `RegexDetector` pattern sets shipped in `examples/detectors/`. Each file exposes a `PATTERNS` dictionary and a `create_detector()` helper.

For recipes (how to compose, combine with GLiNER2, add your own), see [Pre-built detectors usage](../examples/detectors.md).

---

## Common (universal)

**File:** `examples/detectors/common.py`

| Label | Example match |
|-------|---------------|
| `EMAIL` | `alice@example.com` |
| `IP_V4` | `192.168.1.42` |
| `IP_V6` | `2001:0db8:85a3::8a2e:0370:7334` |
| `URL` | `https://api.example.com/v1` |
| `CREDIT_CARD` | `4532-1234-5678-9012` |
| `PHONE_INTERNATIONAL` | `+33 6 12 34 56 78` |
| `OPENAI_API_KEY` | `sk-proj-abc123xyz456789ABCDEF` |
| `AWS_ACCESS_KEY` | `AKIAIOSFODNN7EXAMPLE` |
| `GITHUB_TOKEN` | `ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ...` |
| `STRIPE_KEY` | `sk_live_ABCDEFGHIJKLMNOPQR...` |

---

## US-specific

**File:** `examples/detectors/us.py`

| Label | Example match | Format |
|-------|---------------|--------|
| `US_SSN` | `123-45-6789` | XXX-XX-XXXX |
| `US_PHONE` | `(555) 867-5309` | With optional +1 prefix |
| `US_PASSPORT` | `C12345678` | Letter + 8 digits |
| `US_ZIP_CODE` | `90210-1234` | ZIP or ZIP+4 |
| `US_EIN` | `12-3456789` | Employer Identification Number |
| `US_BANK_ROUTING` | `021000021` | 9-digit ABA routing number |

---

## Europe

**File:** `examples/detectors/europe.py`

| Label | Example match | Country |
|-------|---------------|---------|
| `EU_IBAN` | `FR7630006000011234567890189` | Pan-EU |
| `EU_VAT` | `FR12345678901` | Pan-EU |
| `FR_SSN` | `185017512345612` | France (INSEE) |
| `FR_PHONE` | `06 12 34 56 78` | France |
| `FR_ZIP` | `75001` | France |
| `DE_PHONE` | `030 1234567` | Germany |
| `DE_ZIP` | `10115` | Germany |
| `UK_NINO` | `AB123456C` | UK (National Insurance) |
| `UK_NHS` | `943-476-5919` | UK (NHS number) |
| `UK_POSTCODE` | `SW1A 1AA` | UK |
