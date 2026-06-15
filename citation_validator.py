#!/usr/bin/env python3
"""
Citation DOI Validator - Academic Citation Verification Tool

Verifies citations in BibTeX files by checking:
1. DOI validity and accessibility (CrossRef, doi.org)
2. Author name accuracy (fuzzy matching)
3. Title matching
4. Publication year/venue accuracy
5. Cross-reference with academic databases (Semantic Scholar, OpenAlex, DBLP, CrossRef)
6. Reverse lookup of DOI-less entries by title/author/year (OpenAlex, CrossRef, DBLP)

Author: Lalit Narayan Mishra
License: MIT
Repository: https://github.com/lnm8910/citation-doi-validator
"""

import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

# Suppress the urllib3 LibreSSL warning that fires on macOS-system-Python the moment
# urllib3 is imported. This must run *before* `import requests`.
warnings.filterwarnings("ignore", message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+")

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


__version__ = "1.2.0"
__author__ = "Lalit Narayan Mishra"


RATE_LIMIT_SECONDS = 0.5

LAST_NAME_MATCH_THRESHOLD = 0.9
GIVEN_INITIAL_MUST_AGREE = True
AUTHORS_MATCH_THRESHOLD = 0.8
AUTHORS_FABRICATED_THRESHOLD = 0.5

TITLE_MATCH_THRESHOLD = 0.8

S2_CONFIRMING_TITLE_THRESHOLD = 0.85

# Reverse-lookup (DOI-less confirmation) thresholds. A DOI-less entry is confirmed
# only with high title similarity AND author corroboration, which guards against
# title-collision false positives (e.g. a same-titled but unrelated paper).
REVLOOKUP_TITLE_GATE = 0.80          # min title similarity for a candidate to count
REVLOOKUP_TITLE_CONFIRM = 0.85       # title similarity required to confirm a match
REVLOOKUP_AUTHOR_CORROBORATE = 0.50  # fraction of claimed authors that must agree
REVLOOKUP_CONFIRM_CONFIDENCE = 0.85  # combined confidence required to confirm (MATCHED)
REVLOOKUP_AMBIGUOUS_FLOOR = 0.60     # confidence in [floor, confirm) -> AMBIGUOUS
REVLOOKUP_ROWS = 5                   # candidates requested per source

# OpenAlex polite-pool contact. OpenAlex is the primary reverse-lookup source: free,
# no key, generous limits, and it indexes arXiv plus proceedings with authors + DOIs,
# unlike DBLP / keyless Semantic Scholar which throttle aggressively on batch runs.
OPENALEX_MAILTO = "citation-doi-validator@users.noreply.github.com"

_DOI_URL_PREFIX = re.compile(r'^\s*(?:https?://)?(?:dx\.)?doi\.org/', re.IGNORECASE)


def normalize_doi(raw: Optional[str]) -> str:
    """Normalize a DOI string by stripping URL prefix, whitespace, and surrounding punctuation.

    Returns empty string for None or empty input.
    """
    if not raw:
        return ''
    doi = raw.strip()
    doi = _DOI_URL_PREFIX.sub('', doi)
    doi = doi.strip().strip('<>').strip().rstrip('.,;')
    return doi


def split_name(full: str) -> Tuple[str, str, str]:
    """Split a normalized "given family" name into (given_full, given_initial, family).

    Robust to single-token names (returns family only) and multi-token given names.
    """
    full = full.strip()
    if not full:
        return ('', '', '')
    parts = full.split()
    if len(parts) == 1:
        return ('', '', parts[0])
    family = parts[-1]
    given_full = ' '.join(parts[:-1])
    given_initial = ''
    for ch in given_full:
        if ch.isalpha():
            given_initial = ch.lower()
            break
    return (given_full.lower(), given_initial, family.lower())


class CitationVerifier:
    """
    Verifies citation authenticity using multiple academic APIs

    Attributes:
        verbose (bool): Enable verbose logging
        session (requests.Session): HTTP session for API calls
        crossref_api (str): CrossRef API endpoint
        semantic_scholar_api (str): Semantic Scholar API endpoint
    """

    def __init__(self, verbose=False):
        """
        Initialize Citation Verifier

        Args:
            verbose (bool): Enable verbose logging output
        """
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'CitationDOIValidator/{__version__} (Academic Research Tool)'
        })

        # API endpoints
        self.crossref_api = "https://api.crossref.org/works/"
        self.semantic_scholar_api = "https://api.semanticscholar.org/graph/v1/paper/"

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = RATE_LIMIT_SECONDS

    def log(self, message: str):
        """Print verbose logging with timestamp to stderr (so reports on stdout stay clean)."""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", file=sys.stderr)

    def rate_limit(self):
        """Enforce rate limiting between API calls to respect API quotas"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def parse_bibtex_file(self, filepath: Path) -> List[Dict]:
        """
        Parse BibTeX file and extract citation entries.

        Uses a brace-balanced scanner so titles like ``{{TravisTorrent}: ...}``
        are preserved instead of being truncated at the first inner ``}``.
        """
        self.log(f"Parsing BibTeX file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        entries = []
        i = 0
        n = len(content)

        while i < n:
            at = content.find('@', i)
            if at < 0:
                break
            type_match = re.match(r'@(\w+)\s*\{', content[at:])
            if not type_match:
                i = at + 1
                continue
            entry_type = type_match.group(1)
            cursor = at + type_match.end()

            comma = content.find(',', cursor)
            if comma < 0:
                break
            entry_key = content[cursor:comma].strip()
            cursor = comma + 1

            fields = {'type': entry_type, 'key': entry_key}
            depth = 1
            field_buf = []
            while cursor < n and depth > 0:
                ch = content[cursor]
                if ch == '{':
                    depth += 1
                    field_buf.append(ch)
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        break
                    field_buf.append(ch)
                else:
                    field_buf.append(ch)
                cursor += 1
            fields_str = ''.join(field_buf)

            self._parse_fields(fields_str, fields)
            entries.append(fields)

            i = cursor + 1 if depth == 0 else n

        self.log(f"Found {len(entries)} entries")
        return entries

    def _parse_fields(self, body: str, fields: Dict) -> None:
        """Extract ``name = value`` pairs from a BibTeX entry body, brace-balanced."""
        i = 0
        n = len(body)
        while i < n:
            while i < n and body[i] in ' \t\r\n,':
                i += 1
            if i >= n:
                break
            name_start = i
            while i < n and (body[i].isalnum() or body[i] in '_-'):
                i += 1
            name = body[name_start:i].strip()
            if not name:
                i += 1
                continue
            while i < n and body[i] in ' \t\r\n':
                i += 1
            if i >= n or body[i] != '=':
                continue
            i += 1
            while i < n and body[i] in ' \t\r\n':
                i += 1
            if i >= n:
                break
            if body[i] == '{':
                depth = 1
                i += 1
                value_start = i
                while i < n and depth > 0:
                    if body[i] == '{':
                        depth += 1
                    elif body[i] == '}':
                        depth -= 1
                        if depth == 0:
                            break
                    i += 1
                value = body[value_start:i]
                i += 1
            elif body[i] == '"':
                i += 1
                value_start = i
                while i < n and body[i] != '"':
                    i += 1
                value = body[value_start:i]
                i += 1
            else:
                value_start = i
                while i < n and body[i] not in ',\n':
                    i += 1
                value = body[value_start:i]
            value = value.strip()
            value = self._strip_outer_braces(value)
            fields[name.lower()] = value

    @staticmethod
    def _strip_outer_braces(value: str) -> str:
        """Strip outer protective braces from a BibTeX value (e.g. ``{{Title}}`` -> ``{Title}``).

        Only strips when the entire value is enclosed in a balanced outermost pair.
        """
        if len(value) >= 2 and value[0] == '{' and value[-1] == '}':
            depth = 0
            for idx, ch in enumerate(value):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and idx != len(value) - 1:
                        return value
            return value[1:-1]
        return value

    def clean_author_name(self, name: str) -> str:
        """Normalize an author name for comparison (LaTeX accents stripped, lowercased)."""
        name = re.sub(r'\\[\'"`^~=.]\{(.)\}', r'\1', name)
        name = re.sub(r'\{\\[\'"`^~=.]?(.)\}', r'\1', name)
        name = re.sub(r'\\[\'"`^~=.](.)', r'\1', name)
        name = name.replace('{', '').replace('}', '')
        name = ' '.join(name.split())
        return name.lower()

    def display_author_name(self, name: str) -> str:
        """Like ``clean_author_name`` but preserves original case (used for fix suggestions)."""
        name = re.sub(r'\\[\'"`^~=.]\{(.)\}', r'\1', name)
        name = re.sub(r'\{\\[\'"`^~=.]?(.)\}', r'\1', name)
        name = re.sub(r'\\[\'"`^~=.](.)', r'\1', name)
        name = name.replace('{', '').replace('}', '')
        return ' '.join(name.split())

    def parse_authors(self, author_string: str) -> List[str]:
        """Parse BibTeX author string into list of normalized "given family" names."""
        if not author_string:
            return []
        authors = re.split(r'\s+and\s+', author_string)
        cleaned = []
        for author in authors:
            if ',' in author:
                parts = author.split(',')
                last = parts[0].strip()
                first = parts[1].strip() if len(parts) > 1 else ""
                cleaned.append(f"{first} {last}".strip())
            else:
                cleaned.append(author.strip())
        return [self.clean_author_name(a) for a in cleaned if a]

    def parse_authors_display(self, author_string: str) -> List[str]:
        """Like ``parse_authors`` but preserves original casing — for fix suggestions."""
        if not author_string:
            return []
        authors = re.split(r'\s+and\s+', author_string)
        out = []
        for author in authors:
            if ',' in author:
                parts = author.split(',')
                last = parts[0].strip()
                first = parts[1].strip() if len(parts) > 1 else ""
                out.append(f"{first} {last}".strip())
            else:
                out.append(author.strip())
        return [self.display_author_name(a) for a in out if a]

    def similarity_ratio(self, str1: str, str2: str) -> float:
        """
        Calculate similarity ratio between two strings using SequenceMatcher

        Args:
            str1 (str): First string
            str2 (str): Second string

        Returns:
            float: Similarity ratio (0.0-1.0)
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def verify_via_crossref(self, doi: str) -> Optional[Dict]:
        """
        Verify citation using CrossRef API

        Args:
            doi (str): DOI to verify

        Returns:
            Optional[Dict]: Verification result or error dict
        """
        if not doi:
            return None

        self.log(f"Querying CrossRef for DOI: {doi}")
        self.rate_limit()

        try:
            url = f"{self.crossref_api}{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 404:
                return {'error': 'DOI_NOT_FOUND', 'status_code': 404}

            response.raise_for_status()
            data = response.json()

            if 'message' not in data:
                return {'error': 'INVALID_RESPONSE'}

            message = data['message']

            # Extract relevant fields
            result = {
                'doi': message.get('DOI'),
                'title': message.get('title', [None])[0],
                'authors': [],
                'year': None,
                'venue': None,
                'type': message.get('type'),
                'raw': message
            }

            # Parse authors — store both comparison form (lowercased, accent-stripped)
            # and a display form (preserves casing) for fix suggestions
            result['authors_display'] = []
            if 'author' in message:
                for author in message['author']:
                    family = author.get('family', '')
                    given = author.get('given', '')
                    full_name = f"{given} {family}".strip()
                    result['authors'].append(self.clean_author_name(full_name))
                    result['authors_display'].append(self.display_author_name(full_name))

            # Parse year
            if 'published' in message:
                date_parts = message['published'].get('date-parts', [[]])[0]
                if date_parts:
                    result['year'] = date_parts[0]
            elif 'created' in message:
                date_parts = message['created'].get('date-parts', [[]])[0]
                if date_parts:
                    result['year'] = date_parts[0]

            # Parse venue
            if 'container-title' in message and message['container-title']:
                result['venue'] = message['container-title'][0]
            elif 'publisher' in message:
                result['venue'] = message['publisher']

            return result

        except requests.RequestException as e:
            self.log(f"CrossRef API error: {e}")
            return {'error': 'API_ERROR', 'message': str(e)}

    def verify_via_doi_org(self, doi: str) -> Optional[Dict]:
        """
        Verify DOI existence using doi.org Handle System API

        Fallback for DOIs not indexed by CrossRef (e.g., arXiv preprints)

        Args:
            doi (str): DOI to verify

        Returns:
            Optional[Dict]: Verification result or error dict
        """
        if not doi:
            return None

        self.log(f"Querying doi.org for DOI: {doi}")
        self.rate_limit()

        try:
            # doi.org Handle System API
            url = f"https://doi.org/api/handles/{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 404:
                return {'error': 'DOI_NOT_FOUND', 'status_code': 404}

            if response.status_code != 200:
                return {'error': 'DOI_API_ERROR', 'status_code': response.status_code}

            data = response.json()

            # Check if DOI exists
            if data.get('responseCode') == 1:  # responseCode 1 = success
                result = {
                    'doi': doi,
                    'exists': True,
                    'handle': data.get('handle'),
                    'values': data.get('values', []),
                    'source': 'doi.org'
                }

                # Try to extract URL from handle values
                for value in data.get('values', []):
                    if value.get('type') == 'URL':
                        result['url'] = value.get('data', {}).get('value')
                        break

                self.log(f"DOI {doi} exists in doi.org system")
                return result
            else:
                return {'error': 'DOI_NOT_FOUND', 'responseCode': data.get('responseCode')}

        except requests.RequestException as e:
            self.log(f"doi.org API error: {e}")
            return {'error': 'API_ERROR', 'message': str(e)}

    def verify_via_semantic_scholar(self, title: str, authors: List[str]) -> Optional[Dict]:
        """
        Verify citation using Semantic Scholar API

        Args:
            title (str): Paper title to search
            authors (List[str]): List of author names

        Returns:
            Optional[Dict]: Verification result or error dict
        """
        if not title:
            return None

        self.log(f"Querying Semantic Scholar for: {title[:50]}...")
        self.rate_limit()

        try:
            search_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                'query': title,
                'limit': 1,
                'fields': 'title,authors,year,venue,externalIds'
            }

            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get('data'):
                return {'error': 'NOT_FOUND'}

            paper = data['data'][0]

            result = {
                'title': paper.get('title'),
                'authors': [self.clean_author_name(a['name']) for a in paper.get('authors', [])],
                'year': paper.get('year'),
                'venue': paper.get('venue'),
                'doi': paper.get('externalIds', {}).get('DOI'),
                'raw': paper
            }

            return result

        except requests.RequestException as e:
            self.log(f"Semantic Scholar API error: {e}")
            return {'error': 'API_ERROR', 'message': str(e)}

    # ----- Reverse lookup: confirm DOI-less entries by title/author/year -----

    def _http_get(self, url: str, params: Optional[Dict] = None, timeout: int = 15, max_retries: int = 3):
        """Rate-limited GET with retry and backoff on 429/503 (honoring Retry-After).

        Free metadata APIs (DBLP, CrossRef, Semantic Scholar) throttle bursty batch
        runs; without this a transient 429 was being recorded as "not found" and the
        best source (DBLP for CS papers) was silently lost mid-batch.
        """
        backoff = 1.0
        response = None
        for attempt in range(max_retries + 1):
            self.rate_limit()
            response = self.session.get(url, params=params, timeout=timeout)
            if response.status_code in (429, 503) and attempt < max_retries:
                retry_after = response.headers.get('Retry-After')
                try:
                    wait = float(retry_after) if retry_after else backoff
                except (TypeError, ValueError):
                    wait = backoff
                wait = min(max(wait, backoff), 10.0)
                self.log(f"HTTP {response.status_code} from {url.split('/')[2]}; backing off {wait:.1f}s")
                time.sleep(wait)
                backoff *= 2
                continue
            return response
        return response

    def _candidate_from_crossref_item(self, item: Dict) -> Dict:
        """Map a CrossRef /works search item to a normalized candidate dict."""
        authors, authors_display = [], []
        for a in item.get('author', []) or []:
            full = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if full:
                authors.append(self.clean_author_name(full))
                authors_display.append(self.display_author_name(full))
        year = None
        issued = item.get('issued', {}).get('date-parts', [[None]])
        if issued and issued[0]:
            year = issued[0][0]
        return {
            'title': (item.get('title') or [None])[0],
            'authors': authors,
            'authors_display': authors_display,
            'year': year,
            'venue': (item.get('container-title') or [None])[0],
            'doi': normalize_doi(item.get('DOI')),
            'type': item.get('type'),
            'source': 'crossref-search',
        }

    def verify_via_crossref_search(self, title: str, rows: int = REVLOOKUP_ROWS) -> Optional[List[Dict]]:
        """Reverse lookup: find candidate works in CrossRef by bibliographic query.

        Returns a list of candidate dicts (possibly empty) on success, or None on a
        network error, so callers can tell "searched, found nothing" from "could not
        search".
        """
        if not title:
            return []
        self.log(f"Querying CrossRef search for: {title[:50]}...")
        try:
            params = {
                'query.bibliographic': title,
                'rows': rows,
                'select': 'DOI,title,author,issued,container-title,type',
            }
            response = self._http_get("https://api.crossref.org/works", params=params)
            response.raise_for_status()
            items = response.json().get('message', {}).get('items', [])
            return [self._candidate_from_crossref_item(it) for it in items]
        except (requests.RequestException, ValueError) as e:
            self.log(f"CrossRef search error: {e}")
            return None

    def _candidate_from_dblp_info(self, info: Dict) -> Dict:
        """Map a DBLP publication 'info' object to a normalized candidate dict."""
        raw = info.get('authors', {}).get('author', []) if info.get('authors') else []
        if isinstance(raw, dict):
            raw = [raw]
        authors, authors_display = [], []
        for a in raw:
            name = a.get('text') if isinstance(a, dict) else a
            if name:
                name = re.sub(r'\s+\d{3,4}$', '', str(name)).strip()  # drop DBLP homonym digits
                authors.append(self.clean_author_name(name))
                authors_display.append(self.display_author_name(name))
        try:
            year = int(info.get('year')) if info.get('year') else None
        except (TypeError, ValueError):
            year = None
        doi = normalize_doi(info.get('doi'))
        if not doi and info.get('ee'):
            m = re.search(r'(10\.\d{4,9}/\S+)', info.get('ee', ''))
            if m:
                doi = normalize_doi(m.group(1))
        return {
            'title': (info.get('title') or '').rstrip('.'),
            'authors': authors,
            'authors_display': authors_display,
            'year': year,
            'venue': info.get('venue'),
            'doi': doi,
            'type': info.get('type'),
            'source': 'dblp',
        }

    def verify_via_dblp(self, title: str, rows: int = REVLOOKUP_ROWS) -> Optional[List[Dict]]:
        """Reverse lookup: find candidate publications in DBLP by title query.

        DBLP is the authoritative index for computer-science venues and frequently
        carries the DOI even when a BibTeX entry omits it. Returns a list of
        candidates on success, or None on a network error.
        """
        if not title:
            return []
        self.log(f"Querying DBLP for: {title[:50]}...")
        try:
            params = {'q': title, 'format': 'json', 'h': rows}
            response = self._http_get("https://dblp.org/search/publ/api", params=params)
            response.raise_for_status()
            hits = response.json().get('result', {}).get('hits', {}).get('hit', [])
            if isinstance(hits, dict):
                hits = [hits]
            return [self._candidate_from_dblp_info(h.get('info', {})) for h in hits]
        except (requests.RequestException, ValueError) as e:
            self.log(f"DBLP search error: {e}")
            return None

    def _candidate_from_openalex_work(self, work: Dict) -> Dict:
        """Map an OpenAlex work object to a normalized candidate dict."""
        authors, authors_display = [], []
        for a in work.get('authorships', []) or []:
            name = (a.get('author') or {}).get('display_name')
            if name:
                authors.append(self.clean_author_name(name))
                authors_display.append(self.display_author_name(name))
        src = (work.get('primary_location') or {}).get('source') or {}
        return {
            'title': work.get('display_name'),
            'authors': authors,
            'authors_display': authors_display,
            'year': work.get('publication_year'),
            'venue': src.get('display_name'),
            'doi': normalize_doi(work.get('doi')),
            'type': work.get('type'),
            'source': 'openalex',
        }

    def verify_via_openalex(self, title: str, rows: int = REVLOOKUP_ROWS) -> Optional[List[Dict]]:
        """Reverse lookup: find candidate works in OpenAlex by title search.

        OpenAlex is the most batch-friendly free index (no key, high rate limits) and
        covers arXiv and proceedings with authors and DOIs. Returns a list of
        candidates on success, or None on a network error.
        """
        if not title:
            return []
        self.log(f"Querying OpenAlex for: {title[:50]}...")
        # Strip punctuation that would otherwise break the title.search filter syntax.
        clean = re.sub(r'[^\w\s-]', ' ', title).strip()
        # 1) Precise title-only search; 2) fall back to broader full-text search when
        #    the title index returns nothing (the confidence gate keeps precision high).
        queries = (
            {'filter': f'title.search:{clean}', 'per_page': rows, 'mailto': OPENALEX_MAILTO},
            {'search': title, 'per_page': 25, 'mailto': OPENALEX_MAILTO},
        )
        for params in queries:
            try:
                response = self._http_get("https://api.openalex.org/works", params=params)
                response.raise_for_status()
                results = response.json().get('results', [])
            except (requests.RequestException, ValueError) as e:
                self.log(f"OpenAlex search error: {e}")
                return None
            if results:
                return [self._candidate_from_openalex_work(w) for w in results]
        return []  # both queries responded with no results

    @staticmethod
    def _year_proximity(claimed_year, candidate_year) -> float:
        """Return a 0..1 closeness score for two years (neutral 0.5 when unknown)."""
        try:
            cy = int(str(claimed_year).strip())
            ay = int(str(candidate_year).strip())
        except (TypeError, ValueError):
            return 0.5
        diff = abs(cy - ay)
        if diff == 0:
            return 1.0
        if diff == 1:
            return 0.8
        if diff == 2:
            return 0.4
        return 0.0

    def score_metadata_match(self, claimed: Dict, candidate: Dict) -> Dict:
        """Score how well a search candidate matches the claimed citation.

        Combines title similarity (gated), author overlap (reusing compare_authors),
        and year proximity into a single confidence in [0, 1].
        """
        cand_title = (candidate.get('title') or '').strip().rstrip('.')
        claimed_title = (claimed.get('title') or '').strip().rstrip('.')
        if not cand_title or not claimed_title:
            return {'confidence': 0.0, 'title_sim': 0.0, 'author_ratio': 0.0, 'year_close': 0.0}
        title_sim = self.similarity_ratio(claimed_title, cand_title)
        author_cmp = self.compare_authors(claimed.get('authors', []), candidate.get('authors', []))
        author_ratio = author_cmp.get('similarity', 0.0)
        year_close = self._year_proximity(claimed.get('year'), candidate.get('year'))
        if title_sim < REVLOOKUP_TITLE_GATE:
            confidence = title_sim * 0.4  # below the gate this can never be a confident match
        else:
            confidence = 0.50 * title_sim + 0.35 * author_ratio + 0.15 * year_close
        return {
            'confidence': round(confidence, 4),
            'title_sim': round(title_sim, 4),
            'author_ratio': round(author_ratio, 4),
            'year_close': year_close,
        }

    @staticmethod
    def _match_is_confirmed(score: Dict) -> bool:
        """A match is confirmed only with high title similarity AND author corroboration."""
        return (
            score['title_sim'] >= REVLOOKUP_TITLE_CONFIRM
            and score['author_ratio'] >= REVLOOKUP_AUTHOR_CORROBORATE
            and score['confidence'] >= REVLOOKUP_CONFIRM_CONFIDENCE
        )

    def reverse_lookup(self, claimed: Dict) -> Dict:
        """Confirm a DOI-less (or DOI-invalid) citation by searching authoritative
        indexes (DBLP first, then CrossRef) by title and corroborating author/year.

        Returns {status, best, errored, sources_tried} where status is one of
        'matched' | 'ambiguous' | 'not_found' | 'no_title' | 'error'.
        """
        title = claimed.get('title')
        if not title:
            return {'status': 'no_title', 'best': None, 'errored': False, 'sources_tried': []}

        best = None
        sources_tried = []
        errored = False
        for source_fn in (self.verify_via_openalex, self.verify_via_crossref_search, self.verify_via_dblp):
            candidates = source_fn(title)
            if candidates is None:
                errored = True
                continue
            sources_tried.append(candidates[0]['source'] if candidates else 'searched')
            for cand in candidates:
                score = self.score_metadata_match(claimed, cand)
                if best is None or score['confidence'] > best['score']['confidence']:
                    best = {
                        'candidate': cand,
                        'score': score,
                        'source': cand['source'],
                        'confidence': score['confidence'],
                    }
            if best and self._match_is_confirmed(best['score']):
                break  # confident, corroborated match: stop early to save API calls

        if best and self._match_is_confirmed(best['score']):
            status = 'matched'
        elif best and best['confidence'] >= REVLOOKUP_AMBIGUOUS_FLOOR:
            status = 'ambiguous'
        elif not sources_tried:
            status = 'error'
        else:
            status = 'not_found'
        return {'status': status, 'best': best, 'errored': errored, 'sources_tried': sources_tried}

    def compare_authors(self, claimed: List[str], actual: List[str]) -> Dict:
        """Structure-aware author comparison.

        For each claimed author we extract the last name and try to match it (fuzzy
        ≥ ``LAST_NAME_MATCH_THRESHOLD``) against the last name of any actual author.
        When given names are present on both sides we additionally require the first
        initial to agree — this catches fraud where a fraudster keeps a real given
        name but swaps the family name. Score is the fraction of claimed authors
        matched, mapped to VERIFIED / PARTIAL_MATCH / FABRICATED_AUTHORS.
        """
        if not claimed or not actual:
            return {
                'match': False,
                'similarity': 0.0,
                'details': 'Missing author data',
                'matched_count': 0,
                'claimed_count': len(claimed) if claimed else 0,
            }

        actual_split = [split_name(a) for a in actual]

        per_author_matches = []
        for claimed_author in claimed:
            c_given_full, c_initial, c_family = split_name(claimed_author)
            best = 0.0
            for a_given_full, a_initial, a_family in actual_split:
                if not a_family:
                    continue
                fam_sim = self.similarity_ratio(c_family, a_family)
                if fam_sim < LAST_NAME_MATCH_THRESHOLD:
                    continue
                if (
                    GIVEN_INITIAL_MUST_AGREE
                    and c_initial
                    and a_initial
                    and c_initial != a_initial
                ):
                    continue
                best = max(best, fam_sim)
            per_author_matches.append(best >= LAST_NAME_MATCH_THRESHOLD)

        matched_count = sum(1 for ok in per_author_matches if ok)
        ratio = matched_count / len(per_author_matches)

        if ratio >= AUTHORS_MATCH_THRESHOLD:
            details = 'VERIFIED'
            match = True
        elif ratio >= AUTHORS_FABRICATED_THRESHOLD:
            details = 'PARTIAL_MATCH'
            match = False
        else:
            details = 'FABRICATED_AUTHORS'
            match = False

        return {
            'match': match,
            'similarity': ratio,
            'details': details,
            'matched_count': matched_count,
            'claimed_count': len(per_author_matches),
            'claimed': claimed,
            'actual': actual,
        }

    def verify_citation(self, entry: Dict) -> Dict:
        """
        Perform comprehensive verification of a single citation

        Args:
            entry (Dict): Parsed BibTeX entry

        Returns:
            Dict: Comprehensive verification result
        """
        raw_doi = entry.get('doi', '')
        normalized_doi = normalize_doi(raw_doi)
        result = {
            'key': entry.get('key'),
            'type': entry.get('type'),
            'claimed': {
                'title': entry.get('title', ''),
                'authors': self.parse_authors(entry.get('author', '')),
                'authors_display': self.parse_authors_display(entry.get('author', '')),
                'year': entry.get('year', ''),
                'doi': normalized_doi,
                'doi_raw': raw_doi,
                'venue': entry.get('journal') or entry.get('booktitle', '')
            },
            'verification': {
                'doi_valid': None,
                'authors_match': None,
                'title_match': None,
                'year_match': None,
                'overall_status': 'PENDING'
            },
            'issues': [],
            'actual_data': {},
            'original_bibtex_fields': entry
        }

        # 1. Verify via DOI (primary method: CrossRef, fallback: doi.org)
        if result['claimed']['doi']:
            crossref_data = self.verify_via_crossref(result['claimed']['doi'])

            if crossref_data:
                if 'error' in crossref_data:
                    # CrossRef failed - try doi.org as fallback
                    self.log(f"CrossRef failed for {result['claimed']['doi']}, trying doi.org...")
                    doi_org_data = self.verify_via_doi_org(result['claimed']['doi'])

                    if doi_org_data and 'error' not in doi_org_data:
                        # DOI exists in doi.org system - VALID
                        result['verification']['doi_valid'] = True
                        result['verification']['doi_source'] = 'doi.org'
                        result['actual_data']['doi_org'] = doi_org_data
                        if 'notes' not in result:
                            result['notes'] = []
                        result['notes'].append(
                            "DOI verified via doi.org Handle System (not indexed by CrossRef, e.g., arXiv preprint)"
                        )
                        self.log(f"DOI {result['claimed']['doi']} verified via doi.org")
                    else:
                        # DOI doesn't exist in either system
                        result['verification']['doi_valid'] = False
                        result['issues'].append("DOI_NOT_FOUND: Not in CrossRef or doi.org - likely invalid")
                        result['actual_data']['crossref'] = crossref_data
                        if doi_org_data:
                            result['actual_data']['doi_org'] = doi_org_data
                else:
                    # CrossRef success
                    result['verification']['doi_valid'] = True
                    result['verification']['doi_source'] = 'crossref'
                    result['actual_data']['crossref'] = crossref_data

                    # Compare authors
                    author_comparison = self.compare_authors(
                        result['claimed']['authors'],
                        crossref_data.get('authors', [])
                    )
                    result['verification']['authors_match'] = author_comparison

                    if not author_comparison['match']:
                        result['issues'].append(f"AUTHOR_MISMATCH: {author_comparison['details']}")

                    # Compare title
                    if crossref_data.get('title'):
                        title_sim = self.similarity_ratio(
                            result['claimed']['title'],
                            crossref_data['title']
                        )
                        result['verification']['title_match'] = title_sim > 0.8

                        if title_sim < 0.8:
                            result['issues'].append(f"TITLE_MISMATCH: similarity={title_sim:.2f}")

                    # Compare year
                    if crossref_data.get('year'):
                        year_match = str(crossref_data['year']) == str(result['claimed']['year'])
                        result['verification']['year_match'] = year_match

                        if not year_match:
                            result['issues'].append(
                                f"YEAR_MISMATCH: claimed={result['claimed']['year']}, "
                                f"actual={crossref_data['year']}"
                            )

        # 2. No confirmable DOI: confirm by metadata against authoritative indexes.
        #    Semantic Scholar (title), then a corroborated reverse lookup across
        #    DBLP and CrossRef (title plus author plus year).
        s2_confirmed = False
        metadata_match = None
        reverse_status = None
        recovered_doi = None

        if not result['verification']['doi_valid'] and result['claimed']['title']:
            # 2a. Semantic Scholar title search (kept from prior versions).
            s2_data = self.verify_via_semantic_scholar(
                result['claimed']['title'],
                result['claimed']['authors']
            )
            if s2_data and 'error' not in s2_data:
                result['actual_data']['semantic_scholar'] = s2_data
                if s2_data.get('title'):
                    s2_title_sim = self.similarity_ratio(
                        result['claimed']['title'], s2_data['title']
                    )
                    if s2_title_sim >= S2_CONFIRMING_TITLE_THRESHOLD:
                        s2_confirmed = True
                if s2_data.get('doi'):
                    s2_doi_norm = normalize_doi(s2_data['doi'])
                    if result['claimed']['doi']:
                        if s2_doi_norm.lower() != result['claimed']['doi'].lower():
                            # CrossRef said DOI_NOT_FOUND but S2 has a real DOI for this
                            # title: the claimed DOI is wrong (correctable). Replace the
                            # misleading DOI_NOT_FOUND with the actionable DOI_WRONG.
                            result['issues'] = [
                                i for i in result['issues'] if 'DOI_NOT_FOUND' not in i
                            ]
                            result['issues'].append(
                                f"DOI_WRONG: claimed={result['claimed']['doi']}, "
                                f"actual={s2_doi_norm}"
                            )
                    else:
                        recovered_doi = s2_doi_norm

            # 2b. Corroborated reverse lookup (DBLP first, then CrossRef bibliographic).
            rev = self.reverse_lookup(result['claimed'])
            reverse_status = rev['status']
            result['verification']['reverse_lookup_status'] = reverse_status
            if rev['best']:
                cand = rev['best']['candidate']
                result['actual_data']['metadata_match'] = {
                    'source': rev['best']['source'],
                    'confidence': rev['best']['confidence'],
                    'title': cand.get('title'),
                    'authors': cand.get('authors_display') or cand.get('authors'),
                    'year': cand.get('year'),
                    'venue': cand.get('venue'),
                    'doi': cand.get('doi'),
                    'score': rev['best']['score'],
                }
                if reverse_status == 'matched':
                    metadata_match = result['actual_data']['metadata_match']
                    if not recovered_doi and cand.get('doi'):
                        recovered_doi = cand['doi']

        if recovered_doi and not result['claimed']['doi']:
            result['verification']['recovered_doi'] = recovered_doi
        if metadata_match:
            result['verification']['match_source'] = metadata_match['source']
            result['verification']['match_confidence'] = metadata_match['confidence']

        # Determine overall status. A missing DOI that we recovered is a fixable
        # detail, not a defect, so it never degrades the status by itself.
        confirmed_any = (
            bool(result['verification']['doi_valid'])
            or s2_confirmed
            or metadata_match is not None
        )
        result['verification']['confirmed_any_source'] = confirmed_any
        real_issues = [i for i in result['issues'] if not i.startswith('DOI_MISSING')]

        if 'notes' not in result:
            result['notes'] = []

        if any('FABRICATED' in issue for issue in real_issues):
            result['verification']['overall_status'] = 'FABRICATED'
        elif any('DOI_NOT_FOUND' in issue for issue in real_issues):
            result['verification']['overall_status'] = 'DOI_INVALID'
        elif len(real_issues) >= 2:
            result['verification']['overall_status'] = 'SUSPICIOUS'
        elif len(real_issues) == 1:
            result['verification']['overall_status'] = 'WARNING'
        elif result['verification']['doi_valid']:
            result['verification']['overall_status'] = 'VERIFIED'
        elif metadata_match is not None or s2_confirmed:
            # Confirmed by a metadata index rather than by DOI.
            if result['claimed']['doi']:
                result['verification']['overall_status'] = 'VERIFIED'
            else:
                result['verification']['overall_status'] = 'MATCHED'
                src = result['verification'].get('match_source') or 'Semantic Scholar'
                doi_hint = f" Recovered DOI {recovered_doi} is suggested as a fix." if recovered_doi else ""
                result['notes'].append(
                    f"No DOI in entry, but the citation was confirmed by a metadata "
                    f"match against {src}.{doi_hint}"
                )
        elif reverse_status == 'ambiguous':
            result['verification']['overall_status'] = 'AMBIGUOUS'
            best = result['actual_data'].get('metadata_match', {})
            result['notes'].append(
                f"A possible match was found in {best.get('source', 'an index')} "
                f"(confidence {best.get('confidence', 0)}), but author or year "
                f"corroboration was insufficient to confirm it. Manual check recommended."
            )
        elif reverse_status == 'not_found':
            result['verification']['overall_status'] = 'NOT_FOUND'
            result['notes'].append(
                "Searched DBLP and CrossRef by title; no matching record was found. "
                "Verify this citation manually."
            )
        else:
            result['verification']['overall_status'] = 'UNVERIFIED'
            if not result['claimed']['doi']:
                result['notes'].append(
                    "No DOI in entry and authoritative sources could not be reached to "
                    "confirm it. Status is UNVERIFIED, not VERIFIED."
                )
            else:
                result['notes'].append(
                    "No authoritative source confirmed this citation. "
                    "Status is UNVERIFIED."
                )

        return result


def generate_fix_suggestions(result: Dict) -> Dict:
    """
    Generate fix suggestions for a citation with issues

    Args:
        result (Dict): Verification result

    Returns:
        Dict: Fix suggestions with corrected BibTeX entry
    """
    fixes = {
        'has_fixes': False,
        'suggested_authors': None,
        'suggested_doi': None,
        'suggested_title': None,
        'suggested_year': None,
        'bibtex_entry': None
    }

    # Fixes derived from a DOI-matched CrossRef record.
    cf = result['actual_data'].get('crossref')
    if cf and 'error' not in cf:
        # Authors (prefer display-cased names for the suggested fix).
        if 'authors_match' in result['verification']:
            author_match = result['verification']['authors_match']
            if isinstance(author_match, dict) and not author_match.get('match', True):
                actual_authors = cf.get('authors_display') or cf.get('authors', [])
                if actual_authors:
                    fixes['has_fixes'] = True
                    fixes['suggested_authors'] = actual_authors

        # DOI (wrong DOI, or missing DOI that CrossRef supplies).
        if result['claimed']['doi'] and cf.get('doi'):
            if result['claimed']['doi'].lower() != cf.get('doi', '').lower():
                fixes['has_fixes'] = True
                fixes['suggested_doi'] = cf.get('doi')
        elif not result['claimed']['doi'] and cf.get('doi'):
            fixes['has_fixes'] = True
            fixes['suggested_doi'] = cf.get('doi')

        if result['verification'].get('title_match') is False:
            fixes['has_fixes'] = True
            fixes['suggested_title'] = cf.get('title')

        if result['verification'].get('year_match') is False:
            fixes['has_fixes'] = True
            fixes['suggested_year'] = cf.get('year')

    # DOI recovered from a metadata reverse-lookup match (DOI-less entries).
    recovered = result.get('verification', {}).get('recovered_doi')
    if recovered and not result['claimed'].get('doi') and not fixes['suggested_doi']:
        fixes['has_fixes'] = True
        fixes['suggested_doi'] = recovered

    if fixes['has_fixes']:
        fixes['bibtex_entry'] = reconstruct_bibtex_entry(result, fixes)

    return fixes


def reconstruct_bibtex_entry(result: Dict, fixes: Dict) -> str:
    """
    Reconstruct BibTeX entry preserving original fields, applying fixes

    Args:
        result (Dict): Verification result
        fixes (Dict): Fix suggestions

    Returns:
        str: Corrected BibTeX entry
    """
    original_entry = result.get('original_bibtex_fields', {})
    lines = [f"@{result['type']}{{{result['key']},"]

    # Define standard BibTeX field order
    field_order = [
        'author', 'title', 'booktitle', 'journal', 'year', 'month',
        'volume', 'number', 'pages', 'publisher', 'address', 'organization',
        'editor', 'series', 'edition', 'chapter', 'note', 'doi', 'url',
        'isbn', 'issn', 'eprint', 'archivePrefix', 'primaryClass'
    ]

    # Build fields dict
    fields = {}
    for key, value in original_entry.items():
        if key not in ['type', 'key']:
            fields[key.lower()] = value

    # Apply fixes (override original values)
    if fixes.get('suggested_authors'):
        author_str = ' and '.join([
            f"{a.split()[-1]}, {' '.join(a.split()[:-1])}" if len(a.split()) > 1 else a
            for a in fixes['suggested_authors']
        ])
        fields['author'] = author_str

    if fixes.get('suggested_title'):
        fields['title'] = fixes['suggested_title']

    if fixes.get('suggested_year'):
        fields['year'] = str(fixes['suggested_year'])

    if fixes.get('suggested_doi'):
        fields['doi'] = fixes['suggested_doi']

    # Add fields in standard order
    for field_name in field_order:
        if field_name in fields:
            value = fields[field_name]
            lines.append(f"  {field_name} = {{{value}}},")
            del fields[field_name]

    # Add remaining fields
    for field_name, value in sorted(fields.items()):
        lines.append(f"  {field_name} = {{{value}}},")

    lines.append("}")
    return '\n'.join(lines)


def generate_markdown_report(results: List[Dict]) -> str:
    """
    Generate comprehensive Markdown verification report

    Args:
        results (List[Dict]): List of verification results

    Returns:
        str: Markdown-formatted report
    """
    status_emoji = {
        'VERIFIED': '✅',
        'MATCHED': '🟢',
        'UNVERIFIED': '❓',
        'AMBIGUOUS': '🟡',
        'NOT_FOUND': '🔎',
        'WARNING': '⚠️',
        'SUSPICIOUS': '🔍',
        'FABRICATED': '❌',
        'DOI_INVALID': '❌'
    }

    # Calculate statistics
    statuses = {}
    for r in results:
        status = r['verification']['overall_status']
        statuses[status] = statuses.get(status, 0) + 1

    lines = [
        "# Citation Verification Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Total Citations Verified:** {len(results)}",
        "",
        "---",
        "",
        "## Executive Summary",
        ""
    ]

    # Summary table
    lines.extend([
        "| Status | Count | Percentage | Severity |",
        "|--------|-------|------------|----------|"
    ])

    status_order = ['FABRICATED', 'DOI_INVALID', 'SUSPICIOUS', 'WARNING', 'NOT_FOUND', 'AMBIGUOUS', 'UNVERIFIED', 'MATCHED', 'VERIFIED']
    for status in status_order:
        count = statuses.get(status, 0)
        if count > 0:
            percentage = (count / len(results)) * 100
            emoji = status_emoji.get(status, '•')
            severity = 'CRITICAL' if status in ['FABRICATED', 'DOI_INVALID'] else \
                      'HIGH' if status == 'SUSPICIOUS' else \
                      'MEDIUM' if status in ['WARNING', 'NOT_FOUND'] else \
                      'REVIEW' if status in ['AMBIGUOUS', 'UNVERIFIED'] else 'OK'
            lines.append(f"| {emoji} **{status}** | {count} | {percentage:.1f}% | {severity} |")

    lines.extend(["", "---", ""])

    # Key findings
    fabricated = [r for r in results if r['verification']['overall_status'] == 'FABRICATED']
    invalid_doi = [r for r in results if r['verification']['overall_status'] == 'DOI_INVALID']
    suspicious = [r for r in results if r['verification']['overall_status'] == 'SUSPICIOUS']
    not_found = [r for r in results if r['verification']['overall_status'] == 'NOT_FOUND']
    ambiguous = [r for r in results if r['verification']['overall_status'] == 'AMBIGUOUS']
    unverified = [r for r in results if r['verification']['overall_status'] == 'UNVERIFIED']
    matched = [r for r in results if r['verification']['overall_status'] == 'MATCHED']

    lines.append("## Key Findings")
    lines.append("")

    if fabricated:
        lines.append(f"🚨 **{len(fabricated)} FABRICATED citations detected** - Authors do not match actual papers")
    if invalid_doi:
        lines.append(f"🚫 **{len(invalid_doi)} INVALID DOIs** - Citations reference non-existent papers")
    if suspicious:
        lines.append(f"⚠️ **{len(suspicious)} SUSPICIOUS citations** - Multiple discrepancies found")
    if not_found:
        lines.append(f"🔎 **{len(not_found)} NOT_FOUND** - No matching record located in DBLP or CrossRef by title")
    if ambiguous:
        lines.append(f"🟡 **{len(ambiguous)} AMBIGUOUS** - A possible match was found but not corroborated; manual check recommended")
    if unverified:
        lines.append(f"❓ **{len(unverified)} UNVERIFIED citations** - Could not confirm against any authoritative source")
    if matched:
        lines.append(f"🟢 **{len(matched)} MATCHED** - No DOI in the entry, but confirmed via DBLP/CrossRef metadata (DOI recoverable)")

    verified_count = statuses.get('VERIFIED', 0)
    if verified_count > 0:
        lines.append(f"✅ **{verified_count} citations verified** as authentic")

    total_issues = len(fabricated) + len(invalid_doi) + len(suspicious)
    fraud_rate = (total_issues / len(results)) * 100 if results else 0
    lines.extend([
        "",
        f"**Overall Fraud/Error Rate:** {fraud_rate:.1f}%",
        "",
        "---",
        ""
    ])

    # Detailed findings by status
    lines.append("## Detailed Findings")
    lines.append("")

    for status in status_order:
        status_results = [r for r in results if r['verification']['overall_status'] == status]

        if not status_results:
            continue

        emoji = status_emoji.get(status, '•')
        lines.extend([
            f"### {emoji} {status} ({len(status_results)} citations)",
            ""
        ])

        for idx, r in enumerate(status_results, 1):
            lines.extend([
                f"#### {idx}. `{r['key']}`",
                ""
            ])

            # Status badge
            badge_status = status.replace('_', '__')
            badge_color = 'red' if status in ['FABRICATED', 'DOI_INVALID'] else \
                         'orange' if status in ['SUSPICIOUS', 'NOT_FOUND'] else \
                         'yellow' if status in ['WARNING', 'AMBIGUOUS'] else \
                         'lightgrey' if status == 'UNVERIFIED' else \
                         'brightgreen' if status == 'MATCHED' else 'green'
            lines.append(f"![Status](https://img.shields.io/badge/Status-{badge_status}-{badge_color})")
            lines.append("")

            # Claimed information — prefer display-cased names when present
            claimed_authors_disp = r['claimed'].get('authors_display') or r['claimed']['authors']
            lines.extend([
                "**Claimed Information:**",
                "",
                f"- **Title:** {r['claimed']['title']}",
                f"- **Authors:** {', '.join(claimed_authors_disp[:5])}"
            ])

            if len(claimed_authors_disp) > 5:
                lines.append(f"  - *(+{len(claimed_authors_disp) - 5} more authors)*")

            lines.extend([
                f"- **Year:** {r['claimed']['year']}",
                f"- **DOI:** `{r['claimed']['doi'] or 'N/A'}`",
                f"- **Venue:** {r['claimed']['venue']}",
                f"- **Type:** {r['type']}",
                ""
            ])

            # Issues
            if r['issues']:
                lines.extend([
                    "**⚠️ Issues Detected:**",
                    ""
                ])
                for issue in r['issues']:
                    lines.append(f"- 🔴 {issue}")
                lines.append("")

            # Notes (informational)
            if r.get('notes'):
                lines.extend([
                    "**ℹ️ Notes:**",
                    ""
                ])
                for note in r['notes']:
                    lines.append(f"- 📝 {note}")
                lines.append("")

            # Actual data comparison
            if r['actual_data'].get('crossref'):
                cf = r['actual_data']['crossref']
                if 'error' not in cf:
                    actual_authors_disp = cf.get('authors_display') or cf.get('authors', [])
                    lines.extend([
                        "<details>",
                        "<summary><b>Actual Information (from CrossRef)</b></summary>",
                        "",
                        f"- **Title:** {cf.get('title', 'N/A')}",
                        f"- **Authors:** {', '.join(actual_authors_disp[:5])}"
                    ])

                    if len(actual_authors_disp) > 5:
                        lines.append(f"  - *(+{len(actual_authors_disp) - 5} more authors)*")

                    lines.extend([
                        f"- **Year:** {cf.get('year', 'N/A')}",
                        f"- **DOI:** `{cf.get('doi', 'N/A')}`",
                        f"- **Venue:** {cf.get('venue', 'N/A')}",
                        "",
                        "</details>",
                        ""
                    ])

            # Closest match from a metadata reverse-lookup (DBLP / CrossRef search)
            mm = r['actual_data'].get('metadata_match')
            if mm:
                lines.extend([
                    "<details>",
                    f"<summary><b>Closest match (from {mm.get('source', 'index')}, "
                    f"confidence {mm.get('confidence')})</b></summary>",
                    "",
                    f"- **Title:** {mm.get('title', 'N/A')}",
                    f"- **Authors:** {', '.join((mm.get('authors') or [])[:5])}",
                    f"- **Year:** {mm.get('year', 'N/A')}",
                    f"- **DOI:** `{mm.get('doi') or 'N/A'}`",
                    f"- **Venue:** {mm.get('venue', 'N/A')}",
                    "",
                    "</details>",
                    ""
                ])

            # Generate and display fix suggestions (also for DOIs recovered on DOI-less entries)
            if r['issues'] or r.get('verification', {}).get('recovered_doi'):
                fixes = generate_fix_suggestions(r)

                if fixes['has_fixes']:
                    lines.extend([
                        "### 🔧 Suggested Fixes",
                        ""
                    ])

                    if fixes['suggested_authors']:
                        lines.extend([
                            "**Corrected Authors:**",
                            "```"
                        ])
                        lines.append(', '.join(fixes['suggested_authors'][:10]))
                        if len(fixes['suggested_authors']) > 10:
                            lines.append(f"... (+{len(fixes['suggested_authors']) - 10} more)")
                        lines.extend(["```", ""])

                    if fixes['suggested_doi']:
                        lines.append(f"**Corrected DOI:** `{fixes['suggested_doi']}`  ")
                    if fixes['suggested_title']:
                        lines.append(f"**Corrected Title:** {fixes['suggested_title']}  ")
                    if fixes['suggested_year']:
                        lines.append(f"**Corrected Year:** {fixes['suggested_year']}  ")

                    # Show corrected BibTeX entry
                    if fixes['bibtex_entry']:
                        lines.extend([
                            "",
                            "<details>",
                            "<summary><b>📋 Copy-Paste Corrected BibTeX Entry</b></summary>",
                            "",
                            "Replace the entry in `references.bib` with this corrected version:",
                            "",
                            "```bibtex",
                            fixes['bibtex_entry'],
                            "```",
                            "",
                            "</details>",
                            ""
                        ])

            lines.extend(["---", ""])

    # Recommendations
    lines.extend(["## Recommendations", ""])

    if fabricated:
        lines.extend([
            "### 🚨 Critical Actions Required",
            "",
            "The following citations have **fabricated author information**:",
            ""
        ])
        for r in fabricated:
            lines.append(f"- `{r['key']}` - {r['claimed']['title'][:80]}...")
        lines.extend([
            "",
            "**Action:** These citations must be corrected or removed immediately.",
            ""
        ])

    if invalid_doi:
        lines.extend([
            "### 🚫 Invalid DOI References",
            "",
            "The following citations have DOIs that do not exist:",
            ""
        ])
        for r in invalid_doi:
            lines.append(f"- `{r['key']}` - DOI: `{r['claimed']['doi']}`")
        lines.extend([
            "",
            "**Action:** Verify these DOIs are correct or find alternative references.",
            ""
        ])

    # Footer
    lines.extend([
        "---",
        "",
        "## About This Report",
        "",
        "Generated by **Citation DOI Validator** - Academic Citation Verification Tool",
        "",
        "- ✅ Validates DOIs via CrossRef API",
        "- ✅ Verifies author names against academic databases",
        "- ✅ Checks publication metadata (title, year, venue)",
        "- ✅ Uses fuzzy matching to detect variations",
        "- ✅ Cross-references with Semantic Scholar",
        "- ✅ Recovers DOI-less entries via OpenAlex, DBLP, and CrossRef reverse lookup (MATCHED / AMBIGUOUS / NOT_FOUND)",
        "",
        f"**Version:** {__version__}  ",
        f"**Repository:** https://github.com/lnm8910/citation-doi-validator  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Total Citations Analyzed:** {len(results)}",
        ""
    ])

    return "\n".join(lines)


def generate_text_report(results: List[Dict]) -> str:
    """Generate plain text verification report"""
    report_lines = [
        "=" * 80,
        "CITATION VERIFICATION REPORT",
        "=" * 80,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Citations Verified: {len(results)}",
        ""
    ]

    # Summary statistics
    statuses = {}
    for r in results:
        status = r['verification']['overall_status']
        statuses[status] = statuses.get(status, 0) + 1

    report_lines.extend([
        "SUMMARY:",
        "-" * 80
    ])

    for status, count in sorted(statuses.items()):
        percentage = (count / len(results)) * 100
        report_lines.append(f"  {status:15s}: {count:3d} ({percentage:5.1f}%)")

    report_lines.extend(["", "=" * 80, "DETAILED FINDINGS:", "=" * 80, ""])

    # Detailed findings
    for status in ['FABRICATED', 'DOI_INVALID', 'SUSPICIOUS', 'WARNING', 'NOT_FOUND', 'AMBIGUOUS', 'UNVERIFIED', 'MATCHED', 'VERIFIED']:
        status_results = [r for r in results if r['verification']['overall_status'] == status]

        if not status_results:
            continue

        report_lines.append(f"\n{status} ({len(status_results)} citations)")
        report_lines.append('=' * 80)

        for r in status_results:
            report_lines.extend([
                f"\n[{r['key']}]",
                f"Type: {r['type']}",
                f"Status: {r['verification']['overall_status']}",
                ""
            ])

            report_lines.append("CLAIMED:")
            report_lines.append(f"  Title: {r['claimed']['title'][:100]}")
            report_lines.append(f"  Authors: {', '.join(r['claimed']['authors'][:3])}")
            if len(r['claimed']['authors']) > 3:
                report_lines.append(f"           (+{len(r['claimed']['authors']) - 3} more)")
            report_lines.append(f"  Year: {r['claimed']['year']}")
            report_lines.append(f"  DOI: {r['claimed']['doi']}")
            report_lines.append(f"  Venue: {r['claimed']['venue'][:60]}")
            report_lines.append("")

            if r['issues']:
                report_lines.append("ISSUES:")
                for issue in r['issues']:
                    report_lines.append(f"  ⚠ {issue}")
                report_lines.append("")

            if r['actual_data'].get('crossref'):
                cf = r['actual_data']['crossref']
                if 'error' not in cf:
                    report_lines.append("ACTUAL (from CrossRef):")
                    report_lines.append(f"  Title: {cf.get('title', 'N/A')[:100]}")
                    authors = cf.get('authors', [])
                    report_lines.append(f"  Authors: {', '.join(authors[:3])}")
                    if len(authors) > 3:
                        report_lines.append(f"           (+{len(authors) - 3} more)")
                    report_lines.append(f"  Year: {cf.get('year', 'N/A')}")
                    report_lines.append(f"  DOI: {cf.get('doi', 'N/A')}")
                    report_lines.append("")

            report_lines.append("-" * 80)

    return "\n".join(report_lines)


def generate_report(results: List[Dict], output_format='markdown') -> str:
    """
    Generate verification report in specified format

    Args:
        results (List[Dict]): Verification results
        output_format (str): Output format ('text', 'json', 'markdown')

    Returns:
        str: Formatted report
    """
    if output_format == 'json':
        return json.dumps(results, indent=2, ensure_ascii=False)
    elif output_format == 'markdown':
        return generate_markdown_report(results)
    else:
        return generate_text_report(results)


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description='Citation DOI Validator - Verify academic citations in BibTeX files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Verify citations 1-10 (markdown report)
  python citation_validator.py --bib references.bib --start 1 --end 10

  # Generate detailed markdown report with verbose output
  python citation_validator.py --start 1 --end 50 --output report.md --verbose

  # Save results as JSON
  python citation_validator.py --start 1 --end 116 --output report.json --format json

  # Plain text format
  python citation_validator.py --start 1 --end 10 --format text

  # Verify specific citation by key
  python citation_validator.py --key "smith2023paper" --output single.md --verbose

Version: {__version__}
Authors: {__author__}
Repository: https://github.com/lnm8910/citation-doi-validator
        """
    )

    parser.add_argument('--bib', type=str,
                       default='references.bib',
                       help='Path to BibTeX file (default: references.bib)')
    parser.add_argument('--start', type=int,
                       help='Start index (1-based, inclusive)')
    parser.add_argument('--end', type=int,
                       help='End index (1-based, inclusive)')
    parser.add_argument('--key', type=str,
                       help='Verify specific citation by BibTeX key')
    parser.add_argument('--output', '-o', type=str,
                       help='Output file path (default: print to stdout)')
    parser.add_argument('--format', '-f', choices=['text', 'json', 'markdown', 'md'],
                       default='markdown',
                       help='Output format: text, json, markdown/md (default: markdown)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--version', action='version',
                       version=f'Citation DOI Validator v{__version__}')

    args = parser.parse_args()

    # Validate arguments
    if not args.key and (args.start is None or args.end is None):
        parser.error("Must specify either --key or both --start and --end")

    # Initialize verifier
    verifier = CitationVerifier(verbose=args.verbose)

    # Parse BibTeX file
    bib_path = Path(args.bib)
    if not bib_path.exists():
        print(f"Error: BibTeX file not found: {bib_path}", file=sys.stderr)
        sys.exit(1)

    entries = verifier.parse_bibtex_file(bib_path)

    # Select entries to verify
    if args.key:
        entries_to_verify = [e for e in entries if e['key'] == args.key]
        if not entries_to_verify:
            print(f"Error: Citation key not found: {args.key}", file=sys.stderr)
            print(f"Available keys: {', '.join([e['key'] for e in entries[:10]])}...", file=sys.stderr)
            sys.exit(1)
    else:
        # Convert to 0-based indexing
        start_idx = args.start - 1
        end_idx = args.end

        if start_idx < 0 or end_idx > len(entries):
            print(f"Error: Invalid range. File has {len(entries)} entries.", file=sys.stderr)
            sys.exit(1)

        entries_to_verify = entries[start_idx:end_idx]

    print(f"Verifying {len(entries_to_verify)} citations...", file=sys.stderr)

    # Verify each citation
    results = []
    for i, entry in enumerate(entries_to_verify, 1):
        print(f"  [{i}/{len(entries_to_verify)}] Verifying: {entry['key']}", file=sys.stderr)
        result = verifier.verify_citation(entry)
        results.append(result)

    # Normalize format (handle 'md' alias)
    output_format = 'markdown' if args.format == 'md' else args.format

    # Generate report
    report = generate_report(results, output_format=output_format)

    # Output report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding='utf-8')
        print(f"\n✅ Report saved to: {output_path}", file=sys.stderr)
    else:
        print("\n" + report)

    # Print summary to stderr
    statuses = {}
    for r in results:
        status = r['verification']['overall_status']
        statuses[status] = statuses.get(status, 0) + 1

    print("\n" + "=" * 60, file=sys.stderr)
    print("VERIFICATION SUMMARY", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    for status, count in sorted(statuses.items()):
        percentage = (count / len(results)) * 100
        print(f"  {status:15s}: {count:3d} ({percentage:5.1f}%)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Exit with error code if fabrications found
    fabricated = [r for r in results if r['verification']['overall_status'] == 'FABRICATED']
    if fabricated:
        print(f"\n⚠️  WARNING: {len(fabricated)} FABRICATED citations detected!", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
