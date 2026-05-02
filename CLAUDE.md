# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python CLI (`citation_validator.py`) that verifies BibTeX citations against academic APIs to detect fabricated references, invalid DOIs, and metadata mismatches. Distributed both as a runnable script and as an installable package via `setup.py` (entry point: `citation-validator`).

## Common Commands

```bash
# Run against the example BibTeX (smoke test, exercises all three API paths)
python citation_validator.py --bib example_references.bib --start 1 --end 6 --verbose

# Verify a single entry by BibTeX key
python citation_validator.py --bib example_references.bib --key "travistorrent_msr2017" --verbose

# Generate a report (markdown is default; also: json, text, md)
python citation_validator.py --bib example_references.bib --start 1 --end 6 --output report.md --format markdown

# Run the full regression suite after any change (~20s, needs internet)
python tests/run_validation_suite.py
python tests/run_validation_suite.py --suite mutated      # one suite for fast iteration
python tests/run_validation_suite.py --case m3_fab_authors # one case across suites

# Editable install for development
pip install -e .
```

The regression suite is documented in `execution/VALIDATION_SUITE.md` (how to run) and `tests/TEST_SCENARIOS.md` (per-case reference). To add a new test case, edit `tests/expectations.json` and the matching `tests/fixtures/*.bib` (and add a row to `tests/TEST_SCENARIOS.md`). Do **not** add new scripts; the single parameterized runner handles every suite. Cases legitimately allowed to be non-deterministic use a list for `expected` (e.g. `["VERIFIED", "WARNING"]`).

## Architecture

The whole tool lives in one module (`citation_validator.py`, ~1170 lines). The shape that matters:

### Verification cascade (the core logic, in `CitationVerifier.verify_citation`)

The order of API calls is load-bearing — do not reorder without updating status semantics:

1. **CrossRef** (`verify_via_crossref`) — primary. Hit if entry has a DOI. Returns full metadata (title, authors, year, venue) for comparison.
2. **doi.org Handle System** (`verify_via_doi_org`) — fallback used *only* when CrossRef returns an error. Confirms DOI existence (no metadata) for DOIs that aren't in CrossRef (arXiv preprints, institutional DOIs). Marks `doi_source: 'doi.org'` and adds an informational note rather than treating these as second-class.
3. **Semantic Scholar** (`verify_via_semantic_scholar`) — supplementary. Runs only if DOI verification failed *or* the entry has no DOI. Used to suggest a correct DOI via title-based search, never to override CrossRef metadata.

Rate limiting is global (`min_request_interval = 0.5s`, ~2 req/sec) and applies across all three APIs via the shared `rate_limit()` method.

### Status determination (in `verify_citation`, end of function)

Status is derived from `result['issues']` *and* whether any source confirmed the citation. The precedence order is fixed:

1. Any issue containing `FABRICATED` → `FABRICATED` (set by `compare_authors` when matched-fraction < `AUTHORS_FABRICATED_THRESHOLD`)
2. Any issue containing `DOI_NOT_FOUND` → `DOI_INVALID`
3. No issues AND at least one source confirmed → `VERIFIED`
4. No issues AND nothing confirmed → `UNVERIFIED` (was `VERIFIED` pre-1.1; the change closes the no-DOI false-positive class)
5. ≥2 issues → `SUSPICIOUS`
6. 1 issue → `WARNING`

A source "confirms" iff CrossRef / doi.org returned valid metadata for the DOI, or Semantic Scholar's title similarity ≥ `S2_CONFIRMING_TITLE_THRESHOLD` (0.85). These six statuses are referenced by string in `generate_markdown_report` (badge colors, sort order, key findings), `generate_text_report`, and the CLI summary block in `main`. Adding a new status requires updates in all of those.

### Similarity thresholds and constants

All thresholds live at module top so changing them is one-shot:

- `LAST_NAME_MATCH_THRESHOLD` = 0.9 — per-author last-name fuzzy match floor.
- `GIVEN_INITIAL_MUST_AGREE` = True — when both sides have given names, first initials must agree (catches "Smith, Moritz" against "Beller, Moritz" fraud).
- `AUTHORS_MATCH_THRESHOLD` = 0.8 — fraction of claimed authors matched → VERIFIED.
- `AUTHORS_FABRICATED_THRESHOLD` = 0.5 — fraction below which the citation is FABRICATED.
- `TITLE_MATCH_THRESHOLD` = 0.8.
- `S2_CONFIRMING_TITLE_THRESHOLD` = 0.85 — required title similarity for an S2 hit to count as a confirming source.
- `RATE_LIMIT_SECONDS` = 0.5.

Author comparison is **structure-aware** (in `compare_authors`): the validator extracts last names and given-name initials via `split_name`, then matches each claimed author against the actual list by last-name similarity (≥ `LAST_NAME_MATCH_THRESHOLD`) gated on first-initial agreement. The pre-1.1 approach of `SequenceMatcher` over the full "given family" lowercase string is gone — it produced false PARTIAL_MATCH on initials-only entries and false-negative FABRICATED on randomly-named fraud.

Author names are normalized via `clean_author_name` (LaTeX accents stripped, lowercased) for comparison; `display_author_name` keeps original case for fix-suggestion reconstruction. The CrossRef result dict carries both `authors` (comparison) and `authors_display` (display).

### BibTeX parsing

Hand-written brace-balanced scanner (`parse_bibtex_file` + `_parse_fields` + `_strip_outer_braces`). Handles nested braces in field values (e.g. `title = {{TravisTorrent}: ...}`), quoted values (`field = "..."`), unquoted numeric/string values, and trailing commas. `_strip_outer_braces` peels the LaTeX-protective outer brace pair from values like `{{Title}}`. The previous regex-based parser (pre-1.1) silently truncated nested-brace titles at the first inner `}`. Still no support for `@string` macros — out of scope.

### DOI normalization

`normalize_doi(raw)` (module-level) strips `https://(dx.)?doi.org/` prefix, surrounding whitespace, angle brackets, trailing punctuation. Called once in `verify_citation`; the original is kept on `claimed.doi_raw` for echoing in the report. Always feed `claimed.doi` (normalized) to API calls and comparisons.

### Result dict shape

`verify_citation` returns a dict that flows unchanged into all three report generators and the JSON output. Top-level keys: `key`, `type`, `claimed`, `verification`, `issues`, `actual_data`, `original_bibtex_fields`, optional `notes`. `original_bibtex_fields` is the unmodified parsed entry — `reconstruct_bibtex_entry` depends on this to preserve fields the validator doesn't know about (volume, pages, isbn, etc.) when emitting fix suggestions.

## When Modifying

- Adding a new API source: follow the `verify_via_*` pattern (rate-limit, return `{'error': ...}` on failure, return a dict with normalized keys on success). Wire it into the cascade in `verify_citation` — decide explicitly whether it's primary, fallback, or supplementary.
- Adding a new issue string: pick a token that won't collide with the substring checks in the status-determination block (`'FABRICATED'`, `'DOI_NOT_FOUND'`).
- Changing thresholds: there are constants embedded as literals (0.3, 0.8, 0.5s rate limit). Search for them rather than assuming a single config block.
- Report formats: markdown is the default and the most feature-rich (badges, fix suggestions, collapsible sections). Text and JSON are simpler views over the same result dicts.
