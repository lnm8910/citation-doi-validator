# Changelog

All notable changes to Citation DOI Validator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
