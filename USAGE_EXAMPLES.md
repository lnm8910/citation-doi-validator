# Usage Examples - Citation DOI Validator

This document provides practical examples for common use cases.

---

## 📚 Table of Contents

1. [Pre-Submission Verification](#1-pre-submission-verification)
2. [Peer Review Spot-Check](#2-peer-review-spot-check)
3. [Batch Verification](#3-batch-verification)
4. [Specific Citation Check](#4-specific-citation-check)
5. [JSON Output for Automation](#5-json-output-for-automation)
6. [Integration with CI/CD](#6-integration-with-cicd)

---

## 1. Pre-Submission Verification

**Scenario**: You're submitting a paper and want to verify all 120 citations are authentic.

```bash
# Verify all citations with detailed markdown report
python citation_validator.py \
    --bib paper/references.bib \
    --start 1 \
    --end 120 \
    --output verification_report.md \
    --verbose

# Check the report
cat verification_report.md

# If issues found, review them
grep "FABRICATED\|DOI_INVALID\|SUSPICIOUS" verification_report.md
```

**Expected Output**:
```
Verifying 120 citations...
  [1/120] Verifying: smith2023paper
  [2/120] Verifying: doe2022analysis
  ...
  [120/120] Verifying: johnson2021survey

✅ Report saved to: verification_report.md

============================================================
VERIFICATION SUMMARY
============================================================
  VERIFIED       : 115 ( 95.8%)
  WARNING        :   3 (  2.5%)
  SUSPICIOUS     :   2 (  1.7%)
============================================================
```

---

## 2. Peer Review Spot-Check

**Scenario**: You're reviewing a paper and want to verify key citations (strategic sampling).

```bash
# Verify first 15 citations (introduction + key claims)
python citation_validator.py --start 1 --end 15 --output spot_check.md

# Verify specific suspicious citation
python citation_validator.py --key "suspiciousPaper2023" --output suspect.md --verbose

# Quick check (console output only)
python citation_validator.py --start 1 --end 10 --format text
```

**Typical Reviewer Workflow**:
1. Verify 10-15 key citations (most important claims)
2. Spot-check 5 random citations
3. Verify all self-citations (if suspicious)
4. Generate report for editorial team

---

## 3. Batch Verification

**Scenario**: You maintain a large bibliography and want to verify all entries.

```bash
# For large BibTeX files (500+ entries), verify in batches
# Batch 1: Citations 1-100
python citation_validator.py --start 1 --end 100 --output batch1.md

# Batch 2: Citations 101-200
python citation_validator.py --start 101 --end 200 --output batch2.md

# Batch 3: Citations 201-300
python citation_validator.py --start 201 --end 300 --output batch3.md

# OR: Verify all at once (slower, ~8 min for 1000 citations)
python citation_validator.py --start 1 --end 500 --output full_verification.md --verbose
```

**Automation Script** (`verify_all.sh`):
```bash
#!/bin/bash
# Verify entire bibliography in batches

TOTAL=500
BATCH_SIZE=50

for ((start=1; start<=$TOTAL; start+=$BATCH_SIZE)); do
    end=$((start + BATCH_SIZE - 1))
    if [ $end -gt $TOTAL ]; then
        end=$TOTAL
    fi

    echo "Verifying citations $start-$end..."
    python citation_validator.py \
        --start $start \
        --end $end \
        --output "batch_${start}_${end}.md"
done

echo "✅ All batches complete!"
```

---

## 4. Specific Citation Check

**Scenario**: You're unsure about a specific citation's authenticity.

```bash
# Verify by BibTeX key
python citation_validator.py --key "smith2023paper" --output check.md --verbose

# Multiple specific citations
for key in "smith2023" "doe2022" "johnson2021"; do
    python citation_validator.py --key "$key" --output "check_${key}.md"
done
```

**Expected Output**:
```markdown
# Citation Verification Report

## ❌ DOI_INVALID (1 citation)

#### `smith2023paper`

**Issues Detected:**
- 🔴 DOI_NOT_FOUND: Not in CrossRef or doi.org - likely invalid

**Claimed Information:**
- **DOI:** `10.1234/FAKE.2023.999`

**Action:** Verify this DOI is correct or find alternative reference.
```

---

## 5. JSON Output for Automation

**Scenario**: You want to process verification results programmatically.

```bash
# Generate JSON output
python citation_validator.py \
    --start 1 \
    --end 100 \
    --output results.json \
    --format json
```

**Process JSON in Python**:
```python
import json

# Load results
with open('results.json', 'r') as f:
    results = json.load(f)

# Filter fabricated citations
fabricated = [
    r for r in results
    if r['verification']['overall_status'] == 'FABRICATED'
]

print(f"Found {len(fabricated)} fabricated citations:")
for r in fabricated:
    print(f"  - {r['key']}: {r['claimed']['title']}")

# Extract all invalid DOIs
invalid_dois = [
    r['claimed']['doi']
    for r in results
    if r['verification']['overall_status'] == 'DOI_INVALID'
]

print(f"\nInvalid DOIs: {invalid_dois}")
```

**Process JSON with `jq`** (command-line):
```bash
# Count citations by status
cat results.json | jq 'group_by(.verification.overall_status) | map({status: .[0].verification.overall_status, count: length})'

# Extract all DOIs marked as invalid
cat results.json | jq '.[] | select(.verification.overall_status == "DOI_INVALID") | .claimed.doi'

# Get list of verified citations
cat results.json | jq '.[] | select(.verification.overall_status == "VERIFIED") | .key'
```

---

## 6. Integration with CI/CD

**Scenario**: Automatically verify citations on every commit (GitHub Actions).

**`.github/workflows/verify-citations.yml`**:
```yaml
name: Verify Citations

on:
  push:
    paths:
      - 'references.bib'
  pull_request:
    paths:
      - 'references.bib'

jobs:
  verify:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install citation-validator
      run: |
        git clone https://github.com/lnm8910/citation-doi-validator.git
        cd citation-doi-validator
        pip install -r requirements.txt

    - name: Verify citations
      run: |
        cd citation-doi-validator
        python citation_validator.py \
          --bib ../references.bib \
          --start 1 \
          --end 150 \
          --output ../citation_report.md \
          --verbose

    - name: Upload report
      uses: actions/upload-artifact@v3
      with:
        name: citation-verification-report
        path: citation_report.md

    - name: Check for fabricated citations
      run: |
        if grep -q "FABRICATED" citation_report.md; then
          echo "❌ Fabricated citations detected!"
          exit 1
        fi
```

---

## 7. Literature Review Workflow

**Scenario**: Building a systematic literature review with 300+ citations.

```bash
# Step 1: Initial collection (add all citations to references.bib)
# Step 2: First verification pass
python citation_validator.py --start 1 --end 300 --output initial_check.md

# Step 3: Filter by status
grep "DOI_INVALID\|FABRICATED" initial_check.md > critical_issues.txt

# Step 4: Fix critical issues manually in references.bib

# Step 5: Re-verify only fixed citations
python citation_validator.py --start 1 --end 50 --output recheck.md

# Step 6: Final full verification
python citation_validator.py --start 1 --end 300 --output final_report.md --verbose

# Step 7: Archive report with paper
cp final_report.md paper/citation_verification_report.md
```

---

## 8. Quick Quality Check

**Scenario**: Fast check before conference submission deadline.

```bash
# Quick check (console output, no file)
python citation_validator.py --start 1 --end 50

# Only check citations with DOIs
grep 'doi = {' references.bib | wc -l  # Count DOI entries
python citation_validator.py --start 1 --end 40  # Verify those with DOIs
```

---

## 9. Comparing Multiple Papers

**Scenario**: Check citation quality across different papers.

```bash
# Paper 1
python citation_validator.py --bib paper1/refs.bib --start 1 --end 80 \
    --output paper1_report.md

# Paper 2
python citation_validator.py --bib paper2/refs.bib --start 1 --end 120 \
    --output paper2_report.md

# Compare fraud rates
grep "Overall Fraud/Error Rate" paper1_report.md paper2_report.md
```

---

## 10. Advanced: Custom Processing Script

**Scenario**: Build custom verification pipeline.

```python
#!/usr/bin/env python3
"""
Custom verification pipeline with email alerts
"""

from pathlib import Path
from citation_validator import CitationVerifier, generate_report

def verify_and_alert(bib_file, email_to):
    """Verify citations and email report if issues found"""

    # Initialize
    verifier = CitationVerifier(verbose=True)
    entries = verifier.parse_bibtex_file(Path(bib_file))

    # Verify all
    results = []
    for entry in entries:
        result = verifier.verify_citation(entry)
        results.append(result)

    # Check for critical issues
    critical = [r for r in results if r['verification']['overall_status']
                in ['FABRICATED', 'DOI_INVALID']]

    if critical:
        # Generate report
        report = generate_report(results, output_format='markdown')

        # Save locally
        Path('critical_issues.md').write_text(report)

        # Send email (requires email library)
        subject = f"⚠️ {len(critical)} Critical Citation Issues Detected"
        send_email(email_to, subject, report)

        print(f"❌ {len(critical)} critical issues found! Email sent to {email_to}")
        return False
    else:
        print(f"✅ All {len(results)} citations verified!")
        return True

if __name__ == '__main__':
    verify_and_alert('references.bib', 'lnm8910@gmail.com')
```

---

## 11. Testing Example File

**Scenario**: Test the validator with example_references.bib.

```bash
# Included example file has 6 citations with known issues
python citation_validator.py \
    --bib example_references.bib \
    --start 1 \
    --end 6 \
    --output example_report.md \
    --verbose
```

**Expected Results**:
- `travistorrent_msr2017` → ✅ VERIFIED
- `space_framework` → ✅ VERIFIED
- `fake_paper` → ❌ DOI_INVALID
- `dl_cibuild` → ✅ VERIFIED (or ⚠️ WARNING if year varies)
- `attention_is_all_you_need` → ✅ VERIFIED (via doi.org fallback for arXiv)
- `knuth1997art` → ⚠️ WARNING (no DOI - book)

---

## 12. Troubleshooting Common Issues

### Issue: "DOI_NOT_FOUND" for valid DOI

**Cause**: Temporary API outage or rate limiting
**Solution**: Wait 1 minute and re-run
```bash
# Wait and retry
sleep 60
python citation_validator.py --key "problematic_citation" --verbose
```

### Issue: "Author mismatch" for correct authors

**Cause**: Name variations (e.g., "J. Smith" vs "John A. Smith")
**Solution**: Check similarity score
```bash
# Run with verbose to see similarity score
python citation_validator.py --key "citation_key" --verbose
# If similarity > 0.7, it's likely a variation, not an error
```

### Issue: Too many API calls (rate limiting)

**Cause**: Verifying 1000+ citations too fast
**Solution**: Increase delay or batch process
```python
# Edit citation_validator.py, line 47:
self.min_request_interval = 1.0  # Increase from 0.5 to 1.0 seconds
```

---

## 📊 Real-World Case Study

**Paper**: "Build Outcome Prediction for CI/CD" (MDPI AI 2025)

**Task**: Verify 120 citations before submission

```bash
# Full verification
python citation_validator.py \
    --bib mdpi_paper/references.bib \
    --start 1 \
    --end 120 \
    --output mdpi_verification.md \
    --verbose

# Results:
# ✅ VERIFIED: 115 (95.8%)
# ⚠️ WARNING: 3 (2.5%)
# 🔍 SUSPICIOUS: 2 (1.7%)
# ❌ DOI_INVALID: 0 (0.0%)
# ❌ FABRICATED: 0 (0.0%)

# Overall Fraud/Error Rate: 4.2%
```

**Outcome**:
- Identified 3 citations with minor year mismatches (preprint vs final)
- Identified 2 citations with partial author name issues (initials vs full names)
- All fixed before submission
- **Result**: Paper accepted with no citation issues flagged by reviewers

---

## 🎯 Best Practices

### 1. **Verify Early and Often**
```bash
# Don't wait until submission deadline
# Verify after adding every 10-20 citations
python citation_validator.py --start 1 --end 20 --output check1.md
# Add more citations...
python citation_validator.py --start 1 --end 40 --output check2.md
```

### 2. **Use Verbose Mode for Debugging**
```bash
# Always use --verbose when investigating issues
python citation_validator.py --key "problematic" --verbose
```

### 3. **Save Reports with Timestamps**
```bash
# Include timestamp in filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
python citation_validator.py --start 1 --end 100 \
    --output "verification_${TIMESTAMP}.md"
```

### 4. **Check Critical Citations Manually**
```bash
# Even with ✅ VERIFIED status, manually check:
# - Self-citations (potential bias)
# - Key methodology citations (critical to your work)
# - Recent citations (may have metadata lag)
```

### 5. **Document Your Verification**
```bash
# Keep verification reports with your paper
mkdir -p paper/verification_reports
python citation_validator.py --start 1 --end 150 \
    --output paper/verification_reports/$(date +%Y%m%d)_verification.md
```

---

## 🔄 Continuous Verification Workflow

**For Active Research Projects**:

```bash
# Week 1: Initial verification
python citation_validator.py --start 1 --end 50 --output week1.md

# Week 2: Re-verify + new citations
python citation_validator.py --start 1 --end 75 --output week2.md

# Week 3: Full verification before submission
python citation_validator.py --start 1 --end 120 --output final.md --verbose

# After peer review: Verify new citations added during revision
python citation_validator.py --start 121 --end 135 --output revision.md
```

---

## 📧 Contact for Help

**Issues with examples?**
- 🐛 Report bug: https://github.com/lnm8910/citation-doi-validator/issues
- 💬 Ask question: lnm8910@gmail.com
- 📖 Read docs: See README.md

---

**More examples?** Check the `examples/` directory (if available) or open an issue requesting specific use cases!
