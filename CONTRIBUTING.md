# Contributing to Citation DOI Validator

Thank you for your interest in improving this tool! Contributions are welcome from everyone.

---

## 🚀 Quick Start for Contributors

### 1. Fork and Clone

```bash
# Fork repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR-USERNAME/citation-doi-validator.git
cd citation-doi-validator
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

### 3. Make Changes

```bash
# Create feature branch
git checkout -b feature/your-improvement

# Make your changes
# Edit citation_validator.py or add new features

# Test your changes
python citation_validator.py --bib example_references.bib --start 1 --end 6 --verbose
```

### 4. Submit Pull Request

```bash
# Commit your changes
git add .
git commit -m "Add: Brief description of your improvement"

# Push to your fork
git push origin feature/your-improvement

# Create Pull Request on GitHub
```

---

## 💡 Areas for Contribution

### High-Priority Improvements

1. **Additional API Integrations**
   - PubMed API (for medical/biology papers)
   - arXiv API (for preprints)
   - IEEE Xplore API (for engineering papers)
   - Google Scholar (if possible without scraping)
   - DBLP (for computer science papers)

2. **Enhanced BibTeX Parsing**
   - Use `bibtexparser` library for more robust parsing
   - Handle edge cases (nested braces, special characters)
   - Support BibLaTeX format

3. **Performance Optimization**
   - Parallel API calls (asyncio)
   - Caching (avoid re-querying same DOI)
   - Progress bars (tqdm) for long-running jobs

4. **Testing**
   - Unit tests (pytest)
   - Integration tests with mock API responses
   - Test coverage (pytest-cov)

### Medium-Priority Features

5. **GUI Interface**
   - Web interface (Flask/Streamlit)
   - Desktop app (PyQt/Tkinter)
   - Drag-and-drop BibTeX upload

6. **Reference Manager Integration**
   - Zotero plugin
   - Mendeley integration
   - Export to standard formats

7. **Advanced Reporting**
   - HTML reports with interactive charts
   - PDF export
   - Excel/CSV export for batch analysis

8. **Configuration File**
   - YAML/JSON config for API keys
   - Custom similarity thresholds
   - Whitelist/blacklist venues

### Low-Priority Enhancements

9. **CI/CD Integration**
   - GitHub Actions workflow
   - Pre-commit hook for automatic verification
   - Badge generation for READMEs

10. **Documentation**
    - Video tutorials
    - API documentation (Sphinx)
    - More examples

---

## 🎨 Code Style

### Python Style Guide

Follow PEP 8:
```bash
# Format code
black citation_validator.py

# Check style
flake8 citation_validator.py

# Type checking
mypy citation_validator.py
```

### Docstrings

Use Google-style docstrings:
```python
def verify_citation(self, entry: Dict) -> Dict:
    """
    Perform comprehensive verification of a single citation

    Args:
        entry (Dict): Parsed BibTeX entry with 'key', 'author', 'title', etc.

    Returns:
        Dict: Verification result with status, issues, and actual data

    Raises:
        ValueError: If entry is missing required fields
    """
```

### Commit Messages

Use conventional commits:
```
feat: Add PubMed API integration
fix: Handle special characters in author names
docs: Update README with new examples
test: Add unit tests for author matching
refactor: Improve BibTeX parsing logic
```

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=citation_validator

# Run specific test
pytest tests/test_author_matching.py
```

### Writing Tests

Add tests in `tests/` directory:
```python
# tests/test_verification.py
import pytest
from citation_validator import CitationVerifier

def test_doi_validation():
    verifier = CitationVerifier(verbose=False)
    result = verifier.verify_via_crossref("10.1109/MSR.2017.24")

    assert result is not None
    assert 'error' not in result
    assert result['doi'] == "10.1109/MSR.2017.24"

def test_invalid_doi():
    verifier = CitationVerifier(verbose=False)
    result = verifier.verify_via_crossref("10.1234/FAKE.999")

    assert result is not None
    assert result.get('error') == 'DOI_NOT_FOUND'
```

---

## 📝 Pull Request Guidelines

### Before Submitting PR

- [ ] Code follows PEP 8 style guide
- [ ] All functions have docstrings
- [ ] Tests added for new features
- [ ] Tests pass (`pytest`)
- [ ] README updated (if adding features)
- [ ] CHANGELOG updated (if significant change)
- [ ] No breaking changes (or clearly documented)

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
How did you test this?

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] All tests pass
```

---

## 🐛 Reporting Issues

### Bug Reports

Use this template when reporting bugs:

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command: `python citation_validator.py ...`
2. See error: `...`

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04, macOS 13.1, Windows 11]
- Python version: [e.g., 3.10.5]
- citation-validator version: [e.g., 1.0.0]

**BibTeX Entry** (if applicable)
```bibtex
@article{problematic,
  ...
}
```

**Additional context**
Any other relevant information.
```

### Feature Requests

Use this template for feature requests:

```markdown
**Feature Description**
Clear description of the feature.

**Use Case**
Why is this feature useful? Who would benefit?

**Proposed Solution**
How might this feature be implemented?

**Alternatives Considered**
Any alternative approaches?
```

---

## 🎯 Development Roadmap

### Version 1.1 (Next Release)
- [ ] Add PubMed API integration
- [ ] Implement parallel API calls (asyncio)
- [ ] Add progress bars (tqdm)
- [ ] Unit tests with pytest

### Version 1.2 (Future)
- [ ] Web interface (Streamlit)
- [ ] Export to CSV/Excel
- [ ] GitHub Action workflow

### Version 2.0 (Long-term)
- [ ] GUI desktop app
- [ ] Zotero plugin
- [ ] Machine learning for better author matching

---

## 💬 Questions?

- 📧 Email: lnm8910@gmail.com
- 🐛 Issues: https://github.com/lnm8910/citation-doi-validator/issues
- 💬 Discussions: https://github.com/lnm8910/citation-doi-validator/discussions

---

## 📜 Code of Conduct

### Our Standards

**Positive behavior**:
- ✅ Respectful and constructive feedback
- ✅ Welcoming to newcomers
- ✅ Focusing on what's best for the project
- ✅ Accepting constructive criticism

**Unacceptable behavior**:
- ❌ Harassment or discriminatory language
- ❌ Personal attacks
- ❌ Unconstructive criticism
- ❌ Publishing others' private information

### Enforcement

Project maintainers have the right to remove, edit, or reject contributions that don't follow these guidelines.

---

## 🙏 Thank You!

Thank you for contributing to Citation DOI Validator! Every contribution helps improve research quality and academic integrity.

**Contributors will be recognized** in:
- README.md (Contributors section)
- CHANGELOG.md (version release notes)
- GitHub Contributors page

---

**Happy contributing!** 🚀
