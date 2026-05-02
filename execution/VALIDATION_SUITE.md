# Validation Suite

A regression suite for `citation_validator.py`. Run it any time you change the validator (parser, matchers, status logic, report generators) to catch regressions.

## How to run

```bash
# All suites (~20s, requires internet for the real_world_stable suite)
python tests/run_validation_suite.py

# Single suite (fast iteration while changing one area)
python tests/run_validation_suite.py --suite mutated
python tests/run_validation_suite.py --suite manual_author_edits
python tests/run_validation_suite.py --suite real_world_stable

# Single case across all suites (debugging one regression)
python tests/run_validation_suite.py --case m3_fab_authors

# Forward verbose API logs from the validator
python tests/run_validation_suite.py --verbose
```

Exit code is `0` when every case passes, `1` if any case fails, `2` for a CLI/configuration error.

## What's in the suite

There is one runner (`tests/run_validation_suite.py`) that consumes `tests/expectations.json`. Each entry in that file maps a suite name to a fixture BibTeX file plus a list of cases. Each case asserts the validator returns a specific overall status for a specific BibTeX key.

| Suite | File | Cases | Probes |
|---|---|---|---|
| `mutated` | `tests/fixtures/mutated.bib` | 12 | Parser edge cases, DOI normalization, status determination, fabrication detection. Covers the full transition from BEFORE-bug behavior to AFTER-fix behavior. |
| `manual_author_edits` | `tests/fixtures/manual_author_edits.bib` | 8 | Author-edit fraud regression. Each entry mutates author names against a single real DOI so the matcher is the only variable. Includes the exact case the user originally reported. |
| `real_world_stable` | `tests/fixtures/real_world_stable.bib` | 5 | End-to-end integration with live CrossRef / doi.org / Semantic Scholar. Stable subset extracted from `example_references_1.bib`. |

### What each case probes

The expectations file is the source of truth — `tests/expectations.json`. Each case carries `key`, `expected`, and `probes` fields; the runner prints the probes string on every line so failures are self-explanatory. Sample:

```
[3/12] m3_fab_authors: PASS (FABRICATED)
       — Real DOI + completely fabricated authors must be FABRICATED
```

When a status is legitimately non-deterministic (e.g. a probe whose secondary check depends on title match), `expected` is given as a list of acceptable statuses, e.g. `["VERIFIED", "WARNING"]`.

## Adding a new test case

Two-file change — never add a script:

1. Add the BibTeX entry to the appropriate fixture in `tests/fixtures/` (or create a new fixture file). Annotate the entry with a `% [GROUND TRUTH: ...]` comment so the .bib is self-documenting.
2. Add a case object to the matching suite in `tests/expectations.json`:
   ```json
   {"key": "your_new_key", "expected": "VERIFIED", "probes": "What this case is checking"}
   ```

If you are exercising a new behavior class (e.g. parser bug, new API, new status), create a new suite by adding a new top-level entry to `expectations.json["suites"]` pointing at a new fixture file. The runner picks it up automatically.

## Limitations / known caveats

1. **Network required** for the `real_world_stable` suite. CrossRef / doi.org / Semantic Scholar must be reachable. CI without internet must skip with `--suite mutated --suite manual_author_edits` (call the runner twice).
2. **Upstream DOI registration changes** can flip the expected status of `real_world_stable` cases. If a publisher later registers a DOI we currently expect `DOI_INVALID` for, that case will start failing — the test is correct to fail in that case; update the expectation.
3. **Semantic Scholar variability**: S2 occasionally returns no hit for a title that previously matched. We avoid putting cases in the suite whose status depends solely on S2 behavior; if you must, use a list-form `expected` to admit both outcomes.
4. **Rate limiting**: `RATE_LIMIT_SECONDS = 0.5` in `citation_validator.py` means real-world cases take ~0.5s per API call. The full suite is currently ~18s.
5. **No mocking**: by design. The validator is an integration tool over public APIs; mocks would not catch the kinds of bugs this suite is meant to catch (e.g. response-shape changes from CrossRef).

## Where the artifacts live

```
tests/
├── fixtures/
│   ├── mutated.bib                  # 12 broad probes
│   ├── manual_author_edits.bib      # 8 author-edit probes
│   ├── real_world_stable.bib        # 5 stable real-world probes
│   └── no_trailing_newline.bib      # parser smoke fixture (not in expectations)
├── expectations.json                # case → expected-status mapping
└── run_validation_suite.py          # the only runner
execution/
└── VALIDATION_SUITE.md              # this file
plans/
└── IMPROVEMENTS.md                  # rationale behind why these cases exist
```
