# Vendored reference data

## `icd10cm_terms.json.gz`

ICD-10-CM term index used by `api/icd10.py` as the second-pass check on LLM
condition names (`api/assessment_quality.classify_condition_name`).

| | |
|---|---|
| Edition | ICD-10-CM FY2026 tabular list (April 1, 2026) |
| Codes | 46,881 |
| Terms | 58,616 (descriptions + inclusion terms) |
| Size | ~789 KB gzipped |
| Licence | US Government public domain (CMS/NCHS). No licence or attribution required. |

### Shape

```json
{
  "version": "ICD-10-CM FY2026 (tabular, April 1 2026)",
  "source": "...",
  "terms": { "<normalised term>": "<code>" },
  "codes": { "<code>": "<canonical description>" }
}
```

Terms are normalised at build time: lowercased, bracketed asides stripped,
punctuation collapsed to spaces. `api/icd10.py` applies the identical
normalisation to incoming names, then builds a token inverted index in memory
on first use.

### Why vendored rather than a package or an API

- **No network on the triage path.** A live lookup (e.g. the NLM Clinical
  Tables API) would put an HTTP call inside a patient's assessment — the exact
  problem Fix A removed for the OpenRouter model catalog.
- **No runtime dependency.** The data was extracted from the `simple-icd-10-cm`
  wheel, which bundles the official CMS tabular XML, but nothing from that
  package is imported at runtime.

### Regenerating

ICD-10-CM is revised annually (effective October 1). To refresh:

1. Download the current tabular XML from the
   [CMS ICD-10-CM release](https://www.cms.gov/medicare/coding-billing/icd-10-codes)
   (or `pip download simple-icd-10-cm` and take
   `simple_icd_10_cm/data/icd10c-tabular-*.xml` from the wheel).
2. Point the build script at it and regenerate this file. The script lives in
   the commit that introduced this data; it parses every `<diag>` element for
   `<name>` (code), `<desc>` (description) and `<inclusionTerm>/<note>`
   (synonyms), normalises, and writes gzipped JSON.
3. Run `python manage.py test api.test_icd10_validation` — it asserts both
   that real uncurated conditions resolve and that known fabrications do not.

Bump `version` in the payload so `icd10.get_index()['version']` stays accurate.
