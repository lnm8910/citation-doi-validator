#!/usr/bin/env python3
"""
Validation suite runner for citation_validator.

Loads expectations.json, runs the validator against each fixture BibTeX file,
and asserts every case's status matches its expected status.

Single parameterized entry point. To add a new test case, edit
expectations.json (and the corresponding .bib fixture) — do NOT add a new
script.

Usage:
    python tests/run_validation_suite.py                       # all suites
    python tests/run_validation_suite.py --suite mutated       # one suite
    python tests/run_validation_suite.py --case m3_fab_authors # one case across suites
    python tests/run_validation_suite.py --verbose             # forward verbose logs

Exits 0 if every case passed, 1 otherwise. Network access is required for
suites with "requires_network": true (currently real_world_stable).
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from citation_validator import CitationVerifier  # noqa: E402


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def _load_expectations(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _expected_set(expected: Union[str, List[str]]) -> List[str]:
    return [expected] if isinstance(expected, str) else list(expected)


def _pass_fail(actual: str, expected: Union[str, List[str]]) -> bool:
    return actual in _expected_set(expected)


def _format_expected(expected: Union[str, List[str]]) -> str:
    if isinstance(expected, str):
        return expected
    return " | ".join(expected)


def run_suite(
    suite_name: str,
    suite: Dict,
    verifier: CitationVerifier,
    only_case: Optional[str] = None,
) -> Dict:
    """Run one suite. Returns {'passed': int, 'failed': int, 'failures': [...]}."""
    cases = suite["cases"]
    if only_case:
        cases = [c for c in cases if c["key"] == only_case]
        if not cases:
            return {"passed": 0, "failed": 0, "failures": []}

    bib_path = (THIS_DIR / suite["bib"]).resolve()
    print(f"\n{DIM}=== Suite: {suite_name} ({bib_path.name}) ==={RESET}")
    print(f"{DIM}{suite.get('description', '')}{RESET}")

    if not bib_path.exists():
        print(f"{RED}MISSING fixture: {bib_path}{RESET}")
        return {"passed": 0, "failed": 1, "failures": [(suite_name, "FIXTURE_MISSING")]}

    entries = verifier.parse_bibtex_file(bib_path)
    by_key = {e["key"]: e for e in entries}

    passed = 0
    failed = 0
    failures = []

    for idx, case in enumerate(cases, 1):
        key = case["key"]
        expected = case["expected"]
        probes = case.get("probes", "")

        entry = by_key.get(key)
        if entry is None:
            failed += 1
            failures.append((f"{suite_name}::{key}", "ENTRY_NOT_IN_BIB"))
            print(f"  [{idx}/{len(cases)}] {key}: {RED}FAIL — entry not found in {bib_path.name}{RESET}")
            continue

        result = verifier.verify_citation(entry)
        actual = result["verification"]["overall_status"]
        ok = _pass_fail(actual, expected)
        if ok:
            passed += 1
            print(f"  [{idx}/{len(cases)}] {key}: {GREEN}PASS{RESET} ({actual})  {DIM}— {probes}{RESET}")
        else:
            failed += 1
            issues = ", ".join(result.get("issues", [])) or "(no issues recorded)"
            failures.append((f"{suite_name}::{key}", f"got {actual}, expected {_format_expected(expected)}"))
            print(
                f"  [{idx}/{len(cases)}] {key}: {RED}FAIL{RESET} "
                f"got {RED}{actual}{RESET}, expected {YELLOW}{_format_expected(expected)}{RESET}\n"
                f"        probes: {probes}\n"
                f"        issues: {issues}"
            )

    return {"passed": passed, "failed": failed, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", help="Run only the named suite (e.g. mutated)")
    parser.add_argument("--case", help="Run only the named case across all suites")
    parser.add_argument("--verbose", action="store_true", help="Forward verbose logs from CitationVerifier")
    parser.add_argument(
        "--expectations",
        type=Path,
        default=THIS_DIR / "expectations.json",
        help="Path to expectations.json (default: tests/expectations.json)",
    )
    args = parser.parse_args()

    expectations = _load_expectations(args.expectations)
    suites = expectations["suites"]

    if args.suite and args.suite not in suites:
        print(f"{RED}Unknown suite: {args.suite}. Available: {', '.join(suites)}{RESET}", file=sys.stderr)
        return 2

    verifier = CitationVerifier(verbose=args.verbose)

    start = time.time()
    total_passed = 0
    total_failed = 0
    all_failures = []

    for name, suite in suites.items():
        if args.suite and name != args.suite:
            continue
        outcome = run_suite(name, suite, verifier, only_case=args.case)
        total_passed += outcome["passed"]
        total_failed += outcome["failed"]
        all_failures.extend(outcome["failures"])

    elapsed = time.time() - start
    total = total_passed + total_failed

    print(f"\n{DIM}{'-' * 60}{RESET}")
    if total_failed == 0:
        print(f"{GREEN}ALL {total} CASES PASSED{RESET}  {DIM}({elapsed:.1f}s){RESET}")
        return 0

    print(f"{RED}{total_failed}/{total} CASES FAILED{RESET}  {DIM}({elapsed:.1f}s){RESET}")
    for name, reason in all_failures:
        print(f"  {RED}- {name}: {reason}{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
