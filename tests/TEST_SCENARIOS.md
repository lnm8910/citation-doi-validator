# Test Scenarios

Per-case reference for the regression suite at `tests/run_validation_suite.py`. The machine-readable source of truth is [`tests/expectations.json`](expectations.json); this file is the human-readable mirror. If you add or change a case, update both.

| Field | Meaning |
|---|---|
| **Key** | BibTeX `@type{KEY,...}` identifier in the fixture file |
| **Expected** | Acceptable verification status(es). A list means any one of those statuses passes the test (used where third-party API behavior is legitimately non-deterministic) |
| **What this probes** | The single behavior the case is designed to exercise |

## Suite: `mutated`

**Fixture:** [`fixtures/mutated.bib`](fixtures/mutated.bib)

**Description:** Broad probe set covering parser edge cases, DOI normalization, status determination, and fabrication detection. All entries reuse one real DOI (`10.1109/MSR.2017.24`) so each case isolates a single variable.

| # | Key | Expected | What this probes |
|---|---|---|---|
| 1 | `m1_real` | VERIFIED | Clean control: real DOI plus real authors plus real title |
| 2 | `m2_wrong_year` | WARNING | Year mismatch detection (single issue → WARNING) |
| 3 | `m3_fab_authors` | FABRICATED | Real DOI plus completely fabricated authors must be FABRICATED |
| 4 | `m4_initials_only` | VERIFIED | Initials-only given names must NOT trigger PARTIAL_MATCH |
| 5 | `m5_fake_doi` | DOI_INVALID | Invented DOI returns 404 from CrossRef and doi.org |
| 6 | `m6_whitespace_doi` | DOI_INVALID | Whitespace-padded DOI must still be parsed and queried |
| 7 | `m7_doi_as_url` | VERIFIED | DOI given as full URL (`https://doi.org/...`) must be normalized |
| 8 | `m8_no_doi_fake` | UNVERIFIED | No DOI plus fake title must NOT silently VERIFY |
| 9 | `m9_no_doi_no_title` | UNVERIFIED | Empty entry must NOT silently VERIFY |
| 10 | `m10_unicode_accent` | VERIFIED | LaTeX accents in author names (`{\L}ukasz`) must not break matching |
| 11 | `m11_nested_braces` | VERIFIED | Nested braces in title (`{{TravisTorrent}: ...}`) must be parsed correctly |
| 12 | `m12_multiline` | VERIFIED | Multi-line author field with trailing comma must parse |

## Suite: `manual_author_edits`

**Fixture:** [`fixtures/manual_author_edits.bib`](fixtures/manual_author_edits.bib)

**Description:** Author-edit fraud probes (regression for the originally-reported user bug where manual author name changes were not caught). All entries reuse one real DOI; only the author field is mutated, so the matcher is the only variable.

> **Note on probe titles:** these entries deliberately use a short title (`title = {TravisTorrent}`) instead of the full CrossRef title. This produces a `TITLE_MISMATCH` for every entry, which is why `expected` for clean-author cases includes both `VERIFIED` and `WARNING`. The author check is what is being asserted.

| # | Key | Expected | What this probes |
|---|---|---|---|
| 1 | `e1_real` | VERIFIED \| WARNING | Control. Author check must pass; title noise produces an acceptable WARNING |
| 2 | `e2_one_swap` | SUSPICIOUS \| WARNING | 1 of 3 authors swapped must be flagged |
| 3 | `e3_all_swap` | FABRICATED | All 3 authors fully replaced must be FABRICATED (key regression case) |
| 4 | `e4_last_name_change` | FABRICATED | Subtle fraud: given names kept, last names swapped must be FABRICATED |
| 5 | `e5_extra_author` | SUSPICIOUS \| WARNING | Real authors plus 1 fake prepended must be flagged |
| 6 | `e6_typo_last` | VERIFIED \| WARNING | Single-character typo on last name should still match (≥ 0.9 threshold) |
| 7 | `e7_initials` | VERIFIED \| WARNING | Given names reduced to initials must not trigger AUTHOR_MISMATCH |
| 8 | `e8_shuffled` | VERIFIED \| WARNING | Author order shuffled must pass (matching is order-independent) |

## Suite: `real_world_stable`

**Fixture:** [`fixtures/real_world_stable.bib`](fixtures/real_world_stable.bib)

**Description:** Stable real-world cases pulled from `example_references_1.bib`. Tests integration with live CrossRef, doi.org, and Semantic Scholar. **Requires network access.**

> **Stability caveat:** these expectations depend on upstream DOI registration state at the time the suite was authored. Each `DOI_INVALID` case was confirmed by direct curl against both CrossRef (HTTP 404) and the doi.org Handle API (responseCode 100). If a publisher later registers a previously-missing DOI, the corresponding case will fail and the expectation should be updated.

| # | Key | Expected | What this probes |
|---|---|---|---|
| 1 | `rw_dekimpe1995empirical` | VERIFIED | Real DOI plus initials-only authors: end-to-end verification |
| 2 | `rw_brisset2018models` | DOI_INVALID | DOI returns 404 from both CrossRef and doi.org Handle |
| 3 | `rw_hanssens1980market` | FABRICATED | DOI resolves but to a different paper than claimed |
| 4 | `rw_vallecruz2022twitter` | DOI_INVALID | Another confirmed-404 DOI |
| 5 | `rw_montgomery2015introduction` | UNVERIFIED | No DOI book entry must not silently VERIFY |

## Auxiliary fixtures (not part of the regression run)

| File | Purpose |
|---|---|
| `fixtures/no_trailing_newline.bib` | Manual smoke fixture for the parser (file ending without a trailing newline). Not referenced by `expectations.json` because the case is exercised implicitly by the brace-balanced scanner in every other suite. |

## Coverage matrix

| Behavior class | Covered by |
|---|---|
| Parser: nested braces in title | `m11_nested_braces` |
| Parser: multi-line fields and trailing comma | `m12_multiline` |
| Parser: LaTeX accents in author | `m10_unicode_accent` |
| DOI normalization: URL prefix | `m7_doi_as_url` |
| DOI normalization: whitespace | `m6_whitespace_doi` |
| Status: VERIFIED requires confirmation | `m8_no_doi_fake`, `m9_no_doi_no_title`, `rw_montgomery2015introduction` |
| Status: FABRICATED detection | `m3_fab_authors`, `e3_all_swap`, `e4_last_name_change`, `rw_hanssens1980market` |
| Status: DOI_INVALID detection | `m5_fake_doi`, `m6_whitespace_doi`, `rw_brisset2018models`, `rw_vallecruz2022twitter` |
| Status: WARNING for single issue | `m2_wrong_year` |
| Status: SUSPICIOUS for multiple issues | `e2_one_swap`, `e5_extra_author` |
| Author matcher: initials vs full given | `m4_initials_only`, `e7_initials`, `rw_dekimpe1995empirical` |
| Author matcher: typo tolerance | `e6_typo_last` |
| Author matcher: order-independence | `e8_shuffled` |
| Live API integration | `real_world_stable` suite |

## Gaps (not covered yet)

- Multi-word last names (e.g. "van der Berg", "de la Cruz")
- `@string` macro expansion in BibTeX
- Network failure / 5xx retry behavior
- Performance at > 1000 entries
- BibLaTeX-specific syntax variants

If you add cases for any of the above, update both `expectations.json` and this file.

## Adding a new test case

1. Edit (or create) a fixture under `tests/fixtures/`. Annotate the entry with a `% [GROUND TRUTH: ...]` comment so the .bib is self-documenting.
2. Append a case object to the relevant suite in `tests/expectations.json`:
   ```json
   {"key": "your_new_key", "expected": "VERIFIED", "probes": "What this case is checking"}
   ```
3. Add a row to the corresponding table in this file.
4. Run `python tests/run_validation_suite.py --case your_new_key` to confirm.
