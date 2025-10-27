# Installation Guide - Citation DOI Validator

Quick installation instructions for different platforms and use cases.

---

## 🚀 Quick Install (Recommended)

### Linux / macOS

```bash
# Clone repository
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator

# Install dependencies
pip3 install -r requirements.txt

# Test installation
python3 citation_validator.py --version
```

### Windows

```cmd
REM Clone repository
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator

REM Install dependencies
pip install -r requirements.txt

REM Test installation
python citation_validator.py --version
```

---

## 📦 Installation Options

### Option 1: Direct Use (No Installation)

**Pros**: Quick, no system changes
**Cons**: Must run from repository directory

```bash
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator
pip install -r requirements.txt

# Use directly
python citation_validator.py --help
```

---

### Option 2: Pip Install (Editable Mode)

**Pros**: Use from anywhere, easy development
**Cons**: Requires setuptools

```bash
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator

# Install in editable mode
pip install -e .

# Now you can use from anywhere
citation-validator --help

# OR still use as Python module
python -m citation_validator --help
```

---

### Option 3: System-Wide Install

**Pros**: Available globally for all users
**Cons**: Requires admin/sudo permissions

```bash
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator

# Install globally (Linux/macOS)
sudo pip3 install .

# OR on Windows (run as Administrator)
pip install .

# Use from anywhere
citation-validator --version
```

---

### Option 4: Virtual Environment (Isolated)

**Pros**: No conflicts with other Python packages
**Cons**: Must activate venv each time

```bash
# Create virtual environment
python3 -m venv citation-validator-env
source citation-validator-env/bin/activate  # Linux/Mac
# OR: citation-validator-env\Scripts\activate  # Windows

# Clone and install
git clone https://github.com/lnm8910/citation-doi-validator.git
cd citation-doi-validator
pip install -r requirements.txt

# Use (venv must be activated)
python citation_validator.py --help

# Deactivate when done
deactivate
```

---

## ✅ Verify Installation

### Test Basic Functionality

```bash
# Check version
python citation_validator.py --version
# Expected: Citation DOI Validator v1.0.0

# Check help
python citation_validator.py --help
# Expected: Usage instructions displayed

# Test with example file
python citation_validator.py \
    --bib example_references.bib \
    --start 1 \
    --end 6 \
    --verbose
# Expected: Verifies 6 citations, shows results
```

### Test API Connectivity

```bash
# Verify a known-good DOI
python3 -c "
from citation_validator import CitationVerifier
v = CitationVerifier(verbose=True)
result = v.verify_via_crossref('10.1109/MSR.2017.24')
print('✅ CrossRef API working!' if result and 'error' not in result else '❌ API failed')
"
```

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"

**Solution**:
```bash
pip install requests
# OR
pip install -r requirements.txt
```

### "Permission denied" when installing

**Solution** (Linux/macOS):
```bash
# Use --user flag (install for current user only)
pip install --user -r requirements.txt

# OR use virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "python: command not found"

**Solution**:
```bash
# Try python3 instead
python3 citation_validator.py --version

# OR on Windows
py citation_validator.py --version
```

### "git: command not found"

**Solution**:
- **Linux**: `sudo apt-get install git` (Ubuntu/Debian) or `sudo yum install git` (RHEL/CentOS)
- **macOS**: `xcode-select --install`
- **Windows**: Download from https://git-scm.com/download/win

### API requests timing out

**Solution**:
```bash
# Check internet connection
ping api.crossref.org

# Try with longer timeout (edit citation_validator.py line 137)
response = self.session.get(url, timeout=30)  # Increase from 10 to 30 seconds
```

---

## 🐳 Docker Installation (Advanced)

**For containerized deployment**:

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy tool
COPY citation_validator.py .
COPY example_references.bib .

# Set entry point
ENTRYPOINT ["python", "citation_validator.py"]
CMD ["--help"]
```

```bash
# Build image
docker build -t citation-validator .

# Run
docker run citation-validator --bib example_references.bib --start 1 --end 6
```

---

## 📋 System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **RAM**: 256 MB
- **Disk**: 10 MB (for tool + dependencies)
- **Internet**: Required (for API calls)

### Recommended
- **Python**: 3.10 or higher
- **RAM**: 512 MB+ (for large batch jobs)
- **Disk**: 50 MB (with cache and reports)
- **Bandwidth**: Stable internet connection

### Tested Platforms
- ✅ Ubuntu 22.04 LTS (Python 3.10)
- ✅ macOS 13.0+ (Python 3.10+)
- ✅ Windows 11 (Python 3.10+)
- ✅ Debian 11 (Python 3.9)
- ✅ Fedora 38 (Python 3.11)

---

## 🆘 Need Help?

**Installation issues?**
- 📖 Check troubleshooting section above
- 🐛 Open issue: https://github.com/lnm8910/citation-doi-validator/issues
- 📧 Email: lnm8910@gmail.com

**Ready to use?**
- 📚 See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for practical examples
- 📖 See [README.md](README.md) for complete documentation

---

**Installation should take < 5 minutes. If you encounter issues, please open a GitHub issue!**
