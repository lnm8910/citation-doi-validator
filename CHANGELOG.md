# Changelog

All notable changes to Citation DOI Validator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Planned for v1.1.0
- [ ] PubMed API integration (medical/biology papers)
- [ ] Parallel API calls using asyncio (10x speed improvement)
- [ ] Progress bars with tqdm (better UX for large batches)
- [ ] Unit tests with pytest (90%+ coverage)
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
| **1.0.0** | 2025-01-26 | Initial release with CrossRef + Semantic Scholar + doi.org |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on proposing changes.

---

**Maintained by**: [@lnm8910](https://github.com/lnm8910)
**Repository**: https://github.com/lnm8910/citation-doi-validator
