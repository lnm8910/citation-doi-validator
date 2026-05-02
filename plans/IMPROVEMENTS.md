# Citation DOI Validator — Improvement Plan

This plan was produced by running `citation_validator.py` against the two example BibTeX files plus a hand-crafted mutation set in `debug/mutated.bib`. Every diagnosis below is backed by concrete output in `debug/`.

## Evidence summary

| Run | Input | Result | Notes |
|---|---|---|---|
| Baseline 1 | `example_references.bib` (6 entries) | 5 VERIFIED, 1 DOI_INVALID | Behaves as advertised on small clean set. |
| Baseline 2 | `example_references_1.bib` (33 entries) | 16 VERIFIED, 9 WARNING, 1 SUSPICIOUS, 6 DOI_INVALID, 1 FABRICATED | Many of the 16 "VERIFIED" entries have **no DOI at all**, exposing a major false-positive class. All 9 WARNINGs were spurious AUTHOR_MISMATCH due to initials-vs-full-name. |
| Mutation | `debug/mutated.bib` (12 entries) | 6 VERIFIED, 4 WARNING, 2 DOI_INVALID, **0 FABRICATED** | Even an entry with totally fake authors against a real DOI was downgraded to WARNING. Entries with no DOI and made-up titles (m8, m9) were marked VERIFIED. |

## Diagnosed issues, ranked by severity

### Critical correctness issues

#### C1 — No-DOI / no-match entries marked VERIFIED
**Symptom:** `m8_no_doi_fake` (made-up title, year 2099) and `m9_no_doi_no_title` (empty entry) both → VERIFIED. Same pattern in baseline 2: 16 of 16 "VERIFIED" entries have no DOI in the BibTeX. Validator never raised any issue, so default status fell through to VERIFIED.
**Root cause:** `verify_citation` only adds an issue when a *positive* mismatch is found. An entry that nothing was checked against produces an empty `issues` list, and the final status block treats that as VERIFIED.
**Fix:** Introduce a new status `UNVERIFIED` (or `UNVERIFIABLE`) and assign it whenever no authoritative source confirmed at least one field. Specifically: if neither CrossRef nor doi.org confirmed the DOI, *and* Semantic Scholar did not return a high-confidence match (title similarity ≥ 0.8 AND ≥1 author match), the result must not be VERIFIED.

#### C2 — FABRICATED authors downgraded to WARNING
**Symptom:** `m3_fab_authors` had authors `Doe, Jane Q. and Public, Joe` against a real CrossRef record with `Beller / Gousios / Zaidman`. Output: WARNING with `AUTHOR_MISMATCH: PARTIAL_MATCH`.
**Root cause:** `compare_authors` runs `SequenceMatcher` on full "given family" lowercase strings. Random short strings share many common letters, so the average similarity sits in the 0.3–0.8 band and is labelled `PARTIAL_MATCH` rather than `FABRICATED_AUTHORS`. The 0.3 threshold is too lenient for whole-string Ratcliff/Obershelp similarity.
**Fix:** Make author comparison structure-aware:
1. Extract last name(s) from both claimed and actual authors.
2. A claimed author is *matched* if its last name has similarity ≥ 0.9 to *some* actual last name AND at least the first initial of the given name agrees (when both present).
3. Score the citation as fraction of claimed authors matched. Map: ≥0.8 → match, 0.5–0.8 → PARTIAL_MATCH, <0.5 → FABRICATED.

This single fix solves both C2 (false-negative on fabrication) and the mass false-positive PARTIAL_MATCH on initials-only authors observed in baseline 2 and `m4_initials_only`.

#### C3 — DOI as URL works only by accident
**Symptom:** `m7_doi_as_url` had `doi = {https://doi.org/10.1109/MSR.2017.24}` and verified successfully — but only because CrossRef silently strips the prefix server-side. If CrossRef ever stops doing that, or for the doi.org Handle path (which expects bare DOI), this breaks silently.
**Fix:** Add `_normalize_doi(raw)` that strips: leading/trailing whitespace; `https?://(dx\.)?doi\.org/` prefix; trailing punctuation; surrounding angle brackets. Apply once on parse; store normalized DOI in `claimed.doi`. Keep the original around for echoing in the report only.

### High-priority issues

#### H1 — Verbose log written to stdout, mixing with report output
**Symptom:** Running `--verbose` without `--output` causes log lines like `[14:30:58] Parsing BibTeX file: ...` to appear at the top of the printed report.
**Fix:** `CitationVerifier.log` should `print(..., file=sys.stderr)` — same convention the rest of `main()` already uses for progress output.

#### H2 — BibTeX parser breaks on nested braces
**Symptom:** `m11_nested_braces` title `{{TravisTorrent}: Synthesizing {Travis CI} ...}` was parsed as just `{TravisTorrent` because the field regex `[^}]*` stops at the first `}`.
**Root cause:** `parse_bibtex_file` uses two regexes that cannot represent balanced braces.
**Fix:** Replace the field-extraction regex with a small hand-written brace-balanced scanner: when you see `field_name = `, walk character by character tracking brace depth, ending the value at depth-0 `,` or `}` of the entry. Same scanner can also trim outer braces from the value (LaTeX-protected titles). Avoid pulling in `bibtexparser` to keep the zero-extra-deps property.

#### H3 — Fix-suggestion BibTeX uses lowercased author names
**Symptom:** Suggested entry contains `author = {beller, moritz and gousios, georgios and zaidman, andy}` because `clean_author_name` lowercases for comparison and that lowercase form is what gets stored.
**Fix:** Keep two parallel fields on the parsed CrossRef result: `authors_normalized` (used for comparison only) and `authors_display` (original case from CrossRef family/given), and use the display version when reconstructing BibTeX.

### Medium-priority issues

#### M1 — DOI_NOT_FOUND wording is misleading
**Symptom:** When CrossRef returns 404 *and* Semantic Scholar finds a different DOI for the same title, the report says `DOI_NOT_FOUND: Not in CrossRef or doi.org - likely invalid` AND `DOI_WRONG: claimed=..., actual=...`. The two messages contradict each other: it *is* a known paper, the user just used the wrong DOI string.
**Fix:** When S2 returns a candidate DOI for the same title and the claimed DOI doesn't resolve, replace `DOI_NOT_FOUND` with `DOI_WRONG_BUT_CORRECTABLE` and surface only the suggestion. Keep `DOI_NOT_FOUND` for the case where no source recognizes the paper.

#### M2 — Verbose author-similarity threshold buried as magic numbers
The constants 0.3, 0.5, 0.8 (similarity bands) and 0.5 (rate-limit interval) are scattered as literals. A future maintainer changing thresholds will miss one. Pull them up to module-level constants with names: `AUTHOR_FABRICATED_THRESHOLD`, `AUTHOR_MATCH_THRESHOLD`, `TITLE_MATCH_THRESHOLD`, `RATE_LIMIT_SECONDS`.

#### M3 — No retry on transient API failures
A single 5xx from CrossRef poisons the result. Add one retry with backoff (1s, 2s) for 5xx and connection errors. 4xx (including 404) should not retry — they are authoritative answers.

### Lower-priority / cleanup

- **L1**: SOLID — the file mixes a verifier, three report formatters, a fix generator, a CLI. Splitting is a worthwhile refactor but **out of scope** for this round; we will keep the single-file shape but introduce clear sections (constants block, normalization helpers, verifier, formatters, CLI).
- **L2**: No tests. Add a small `tests/test_validator.py` covering `_normalize_doi`, `parse_authors`, `compare_authors`, and the brace-balanced parser, since these are the modules with the most behavioural change.
- **L3**: `clean_author_name`'s LaTeX-accent regex misses `{\L}`, `{\AA}`, `{\ss}`, etc. — the no-diacritic forms. Extend the regex to also match `\\\\([A-Za-z]+)\\{?\\}?` and map a small dictionary of common LaTeX special letters.
- **L4**: `urllib3` `NotOpenSSLWarning` clutters every run on macOS LibreSSL. Suppress it in the script (it's not actionable for users).

## Plan of action for this round

I will implement: **C1, C2, C3, H1, H2, H3, M1, M2, L4.**
I will skip: **L1 (large refactor), L2 (tests — no test infra exists), L3 (low traffic), M3 (no transient failures observed in this run).**

Acceptance criteria, re-running on `debug/mutated.bib`:

| Entry | Required status after fix |
|---|---|
| m1_real | VERIFIED |
| m2_wrong_year | WARNING |
| m3_fab_authors | **FABRICATED** |
| m4_initials_only | **VERIFIED** (no spurious PARTIAL_MATCH) |
| m5_fake_doi | DOI_INVALID |
| m6_whitespace_doi | DOI_INVALID |
| m7_doi_as_url | VERIFIED |
| m8_no_doi_fake | **UNVERIFIED** (not VERIFIED) |
| m9_no_doi_no_title | **UNVERIFIED** (not VERIFIED) |
| m10_unicode_accent | VERIFIED |
| m11_nested_braces | VERIFIED (parser fixed) |
| m12_multiline | VERIFIED |

And, re-running on `example_references_1.bib`, the count of spurious "PARTIAL_MATCH on full vs initial-only authors" WARNINGs should drop to ~0.
