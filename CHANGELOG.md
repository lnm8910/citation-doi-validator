# Changelog

All notable changes to Citation DOI Validator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-06-13

### Added (reverse lookup for DOI-less entries)
- **Confirm citations that have no DOI by matching them against authoritative indexes**, instead of leaving them `UNVERIFIED`. New sources: OpenAlex (primary; no key, batch-friendly), CrossRef bibliographic `query.bibliographic` search, and DBLP. Queried by title with author and year corroboration.
- **Three new statuses:** `MATCHED` (🟢, no DOI in the entry but the work was confirmed in an index, with the DOI recovered as a fix), `AMBIGUOUS` (🟡, a candidate was found but title/author/year corroboration was below the confirm threshold; needs a human check), and `NOT_FOUND` (🔎, searched and nothing matched; the genuine "could not locate" flag, distinct from "could not check").
- **Confidence-scored matching** (`score_metadata_match`) combining gated title similarity, author overlap (reusing `compare_authors`), and year proximity. A match is confirmed only with title similarity ≥ 0.85 AND author corroboration ≥ 0.5 AND combined confidence ≥ 0.85, which blocks title-collision false positives (verified by unit test and the fake/book regression fixtures).
- **Recovered DOIs are back-filled** into the suggested-fix BibTeX entry, turning a missing-DOI finding into a copy-paste correction.
- **HTTP retry with backoff** (`_http_get`) on 429/503 (honoring `Retry-After`) for the search sources.
- New thresholds: `REVLOOKUP_*` constants and `OPENALEX_MAILTO`.

### Changed
- Status taxonomy is now nine statuses (added MATCHED, AMBIGUOUS, NOT_FOUND). `DOI_MISSING` is treated as a recoverable fix rather than a status-degrading issue. Markdown and text reports render the new statuses, severities, and a "Closest match" panel.
- The no-DOI path is no longer Semantic-Scholar-only; S2 (keyless, heavily throttled) is now one of several corroborating sources, with OpenAlex as the reliable primary.

### Behavior changes that may surprise existing users
- Many entries that previously reported `UNVERIFIED` (no DOI to auto-check) now report `MATCHED` with a recovered DOI, or `NOT_FOUND` if genuinely absent. On a 39-entry real-world ML bibliography this converted 34 `UNVERIFIED`/`WARNING` entries into 34 `MATCHED` (0 false positives on audit), recovering 30 DOIs.

---

## [1.1.0] - 2026-05-02

### Fixed (correctness)
- **Author-edit fraud now detected.** Replaced `SequenceMatcher` over full "given family" strings with structure-aware matching (last-name fuzzy match plus first-initial agreement). Closes the regression where a citation with all authors replaced was downgraded to PARTIAL_MATCH/WARNING instead of FABRICATED.
- **No-DOI entries no longer silently VERIFIED.** Added a new `UNVERIFIED` status. An entry is `VERIFIED` only if at least one source (CrossRef, doi.org Handle, or Semantic Scholar with title similarity ≥ 0.85) actually confirmed it. Previously, an entry with no DOI and no S2 hit fell through to VERIFIED.
- **DOIs given as URLs or with whitespace now normalized.** `normalize_doi()` strips `https://(dx.)?doi.org/` prefixes, surrounding whitespace, angle brackets, and trailing punctuation before any API call.
- **Nested-brace titles parsed correctly.** Replaced the regex BibTeX parser with a brace-balanced scanner. Titles like `{{TravisTorrent}: ...}` are now preserved instead of being truncated at the first inner `}`.
- **Verbose log routed to stderr.** Previously polluted stdout when running without `--output`.
- **DOI_NOT_FOUND wording fixed when S2 has a candidate.** When CrossRef returns 404 but Semantic Scholar finds the right paper with a different DOI, the report now emits a single actionable `DOI_WRONG` instead of contradictory `DOI_NOT_FOUND` plus `DOI_WRONG`.
- **Fix-suggestion BibTeX entries preserve original casing.** CrossRef metadata now carries `authors_display` alongside the comparison-only lowercased `authors`.

### Added
- `UNVERIFIED` status (❓) for citations no source could confirm.
- Module-level threshold constants (`LAST_NAME_MATCH_THRESHOLD`, `AUTHORS_MATCH_THRESHOLD`, `AUTHORS_FABRICATED_THRESHOLD`, `TITLE_MATCH_THRESHOLD`, `S2_CONFIRMING_TITLE_THRESHOLD`, `RATE_LIMIT_SECONDS`).
- Regression test suite at `tests/run_validation_suite.py` driven by `tests/expectations.json` and `tests/fixtures/*.bib`. 25 cases covering parser, DOI normalization, author-fraud detection, and live API integration. Documented in `execution/VALIDATION_SUITE.md`.
- urllib3 LibreSSL warning suppressed at import time.

### Changed
- Status determination now requires positive confirmation for `VERIFIED`. Six statuses total: FABRICATED, DOI_INVALID, SUSPICIOUS, WARNING, UNVERIFIED, VERIFIED.
- Author-similarity bands replaced. Old: avg `SequenceMatcher` < 0.3 → FABRICATED, 0.3–0.8 → PARTIAL, ≥ 0.8 → match. New: per-claimed-author last-name match (≥ 0.9) gated on first-initial agreement; matched fraction ≥ 0.8 → VERIFIED, ≥ 0.5 → PARTIAL, < 0.5 → FABRICATED.

### Behavior changes that may surprise existing users
- Some entries that previously reported `VERIFIED` will now report `UNVERIFIED`. This is an intentional correctness fix; an entry without a DOI or matching S2 record was never actually verified, just silently passed.
- Some entries that previously reported `WARNING` (PARTIAL_MATCH from initials-only authors) will now report `VERIFIED`. The new author matcher correctly handles "Smith, J." vs "John Smith".

---

## [1.0.0] - 2025-01-26

### Added
- ✨ Initial release of Citation DOI Validator
- ✅ CrossRef API integration for DOI verification
- ✅ doi.org Handle System fallback for non-CrossRef DOIs (arXiv, institutional)
- ✅ Semantic Scholar API integration for title-based verification
- ✅ Fuzzy author name matching with configurable thresholds
- ✅ Comprehensive metadata validation (title, authors, year, venue)
- ✅ Auto-fix generation with corrected BibTeX entries
- ✅ Multiple output formats (Markdown, JSON, plain text)
- ✅ Rate limiting to respect API quotas
- ✅ Batch processing support (verify 1 to 1000+ citations)
- ✅ Detailed reports with status badges and collapsible sections
- ✅ Command-line interface with flexible options
- ✅ Example BibTeX file for testing
- ✅ Comprehensive documentation (README, USAGE_EXAMPLES, CONTRIBUTING)
- ✅ setup.py for pip installation
- ✅ MIT License

### Verification Status Levels
- ✅ VERIFIED - All checks passed
- ⚠️ WARNING - 1 minor issue detected
- 🔍 SUSPICIOUS - 2+ issues detected
- ❌ DOI_INVALID - DOI does not exist
- ❌ FABRICATED - Authors completely wrong

### APIs Supported
- CrossRef API (primary DOI verification)
- doi.org Handle System (fallback for all registered DOIs)
- Semantic Scholar (supplementary title-based verification)

---

## [Unreleased]

### Planned for v1.2.0
- [ ] PubMed API integration (medical/biology papers)
- [ ] Parallel API calls using asyncio (10x speed improvement)
- [ ] Progress bars with tqdm (better UX for large batches)
- [ ] Caching layer (avoid re-querying same DOIs)

### Planned for v1.2.0
- [ ] Web interface with Streamlit/Flask
- [ ] CSV/Excel export for batch analysis
- [ ] HTML reports with interactive charts
- [ ] Configuration file support (YAML/JSON)
- [ ] GitHub Action workflow template

### Planned for v2.0.0
- [ ] GUI desktop application (PyQt/Tkinter)
- [ ] Zotero plugin integration
- [ ] Machine learning for improved author matching
- [ ] Support for BibLaTeX format
- [ ] Multi-language support (non-English citations)

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| **1.1.0** | 2026-05-02 | Author-fraud detection rewrite, UNVERIFIED status, brace-balanced parser, regression suite |
| **1.0.0** | 2025-01-26 | Initial release with CrossRef + Semantic Scholar + doi.org |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on proposing changes.

---

**Maintained by**: [@lnm8910](https://github.com/lnm8910)
**Repository**: https://github.com/lnm8910/citation-doi-validator
