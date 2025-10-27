#!/usr/bin/env python3
"""
Citation DOI Validator - Academic Citation Verification Tool

Verifies citations in BibTeX files by checking:
1. DOI validity and accessibility (CrossRef, doi.org)
2. Author name accuracy (fuzzy matching)
3. Title matching
4. Publication year/venue accuracy
5. Cross-reference with academic databases (Semantic Scholar)

Author: Lalit Narayan Mishra, Amit Rangari, Sandesh Nagrare, Saroj Kumar Nayak
License: MIT
Repository: https://github.com/lnm8910/citation-doi-validator
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from difflib import SequenceMatcher

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


__version__ = "1.0.0"
__author__ = "Lalit Narayan Mishra, Amit Rangari, Sandesh Nagrare, Saroj Kumar Nayak"


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
        self.min_request_interval = 0.5  # seconds between requests

    def log(self, message: str):
        """Print verbose logging with timestamp"""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def rate_limit(self):
        """Enforce rate limiting between API calls to respect API quotas"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def parse_bibtex_file(self, filepath: Path) -> List[Dict]:
        """
        Parse BibTeX file and extract citation entries

        Args:
            filepath (Path): Path to BibTeX file

        Returns:
            List[Dict]: List of citation entries with parsed fields
        """
        self.log(f"Parsing BibTeX file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Simple regex-based BibTeX parser
        entry_pattern = r'@(\w+)\{([^,]+),\s*(.*?)\n\}'
        entries = []

        for match in re.finditer(entry_pattern, content, re.DOTALL):
            entry_type, entry_key, fields_str = match.groups()

            # Parse fields
            fields = {'type': entry_type, 'key': entry_key}
            field_pattern = r'(\w+)\s*=\s*\{([^}]*)\}'

            for field_match in re.finditer(field_pattern, fields_str):
                field_name, field_value = field_match.groups()
                fields[field_name.lower()] = field_value.strip()

            entries.append(fields)

        self.log(f"Found {len(entries)} entries")
        return entries

    def clean_author_name(self, name: str) -> str:
        """
        Normalize author name for comparison (removes LaTeX commands, whitespace)

        Args:
            name (str): Raw author name

        Returns:
            str: Cleaned, lowercase author name
        """
        # Remove LaTeX accent commands like \"{a}, \'{e}, etc.
        name = re.sub(r'\\[\'"`^~=.]{0,1}\{(.)\}', r'\1', name)
        name = re.sub(r'\\[\'"`^~=.](.)', r'\1', name)

        # Remove extra whitespace
        name = ' '.join(name.split())

        # Convert to lowercase for comparison
        return name.lower()

    def parse_authors(self, author_string: str) -> List[str]:
        """
        Parse BibTeX author string into list of normalized names

        Args:
            author_string (str): BibTeX author field (e.g., "Smith, John and Doe, Jane")

        Returns:
            List[str]: List of cleaned author names
        """
        if not author_string:
            return []

        # Split by 'and'
        authors = re.split(r'\s+and\s+', author_string)

        # Clean each author name
        cleaned = []
        for author in authors:
            # Extract last name (after comma if present)
            if ',' in author:
                parts = author.split(',')
                last = parts[0].strip()
                first = parts[1].strip() if len(parts) > 1 else ""
                cleaned.append(f"{first} {last}".strip())
            else:
                cleaned.append(author.strip())

        return [self.clean_author_name(a) for a in cleaned if a]

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

            # Parse authors
            if 'author' in message:
                for author in message['author']:
                    family = author.get('family', '')
                    given = author.get('given', '')
                    full_name = f"{given} {family}".strip()
                    result['authors'].append(self.clean_author_name(full_name))

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

    def compare_authors(self, claimed: List[str], actual: List[str]) -> Dict:
        """
        Compare claimed vs actual authors using fuzzy string matching

        Args:
            claimed (List[str]): Authors from BibTeX entry
            actual (List[str]): Authors from database

        Returns:
            Dict: Match result with similarity score and details
        """
        if not claimed or not actual:
            return {
                'match': False,
                'similarity': 0.0,
                'details': 'Missing author data'
            }

        # Check if any claimed author appears in actual authors
        matches = []
        for claimed_author in claimed:
            best_match = max([self.similarity_ratio(claimed_author, actual_author)
                            for actual_author in actual], default=0.0)
            matches.append(best_match)

        avg_similarity = sum(matches) / len(matches) if matches else 0.0

        # Determine match status
        if avg_similarity < 0.3:
            return {
                'match': False,
                'similarity': avg_similarity,
                'details': 'FABRICATED_AUTHORS',
                'claimed': claimed,
                'actual': actual
            }
        elif avg_similarity < 0.8:
            return {
                'match': False,
                'similarity': avg_similarity,
                'details': 'PARTIAL_MATCH',
                'claimed': claimed,
                'actual': actual
            }
        else:
            return {
                'match': True,
                'similarity': avg_similarity,
                'details': 'VERIFIED',
                'claimed': claimed,
                'actual': actual
            }

    def verify_citation(self, entry: Dict) -> Dict:
        """
        Perform comprehensive verification of a single citation

        Args:
            entry (Dict): Parsed BibTeX entry

        Returns:
            Dict: Comprehensive verification result
        """
        result = {
            'key': entry.get('key'),
            'type': entry.get('type'),
            'claimed': {
                'title': entry.get('title', ''),
                'authors': self.parse_authors(entry.get('author', '')),
                'year': entry.get('year', ''),
                'doi': entry.get('doi', ''),
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

        # 2. Fallback: Verify via Semantic Scholar (if DOI validation failed or no DOI)
        if not result['verification']['doi_valid'] and result['claimed']['title']:
            s2_data = self.verify_via_semantic_scholar(
                result['claimed']['title'],
                result['claimed']['authors']
            )

            if s2_data and 'error' not in s2_data:
                result['actual_data']['semantic_scholar'] = s2_data

                # If we found a DOI via S2, check if it matches claimed DOI
                if s2_data.get('doi'):
                    if result['claimed']['doi']:
                        if s2_data['doi'].lower() != result['claimed']['doi'].lower():
                            result['issues'].append(
                                f"DOI_WRONG: claimed={result['claimed']['doi']}, "
                                f"actual={s2_data['doi']}"
                            )
                    else:
                        result['issues'].append(f"DOI_MISSING: actual={s2_data['doi']}")

        # Determine overall status
        if not result['issues']:
            result['verification']['overall_status'] = 'VERIFIED'
        elif any('FABRICATED' in issue for issue in result['issues']):
            result['verification']['overall_status'] = 'FABRICATED'
        elif any('DOI_NOT_FOUND' in issue for issue in result['issues']):
            result['verification']['overall_status'] = 'DOI_INVALID'
        elif len(result['issues']) >= 2:
            result['verification']['overall_status'] = 'SUSPICIOUS'
        else:
            result['verification']['overall_status'] = 'WARNING'

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

    # Get actual data from CrossRef
    if result['actual_data'].get('crossref') and 'error' not in result['actual_data']['crossref']:
        cf = result['actual_data']['crossref']

        # Check if authors need fixing
        if 'authors_match' in result['verification']:
            author_match = result['verification']['authors_match']
            if isinstance(author_match, dict) and not author_match.get('match', True):
                actual_authors = cf.get('authors', [])
                if actual_authors:
                    fixes['has_fixes'] = True
                    fixes['suggested_authors'] = actual_authors

        # Check if DOI needs fixing
        if result['claimed']['doi'] and cf.get('doi'):
            if result['claimed']['doi'].lower() != cf.get('doi', '').lower():
                fixes['has_fixes'] = True
                fixes['suggested_doi'] = cf.get('doi')
        elif not result['claimed']['doi'] and cf.get('doi'):
            fixes['has_fixes'] = True
            fixes['suggested_doi'] = cf.get('doi')

        # Check if title needs fixing
        if result['verification'].get('title_match') is False:
            fixes['has_fixes'] = True
            fixes['suggested_title'] = cf.get('title')

        # Check if year needs fixing
        if result['verification'].get('year_match') is False:
            fixes['has_fixes'] = True
            fixes['suggested_year'] = cf.get('year')

        # Generate corrected BibTeX entry
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

    status_order = ['FABRICATED', 'DOI_INVALID', 'SUSPICIOUS', 'WARNING', 'VERIFIED']
    for status in status_order:
        count = statuses.get(status, 0)
        if count > 0:
            percentage = (count / len(results)) * 100
            emoji = status_emoji.get(status, '•')
            severity = 'CRITICAL' if status in ['FABRICATED', 'DOI_INVALID'] else \
                      'HIGH' if status == 'SUSPICIOUS' else \
                      'MEDIUM' if status == 'WARNING' else 'OK'
            lines.append(f"| {emoji} **{status}** | {count} | {percentage:.1f}% | {severity} |")

    lines.extend(["", "---", ""])

    # Key findings
    fabricated = [r for r in results if r['verification']['overall_status'] == 'FABRICATED']
    invalid_doi = [r for r in results if r['verification']['overall_status'] == 'DOI_INVALID']
    suspicious = [r for r in results if r['verification']['overall_status'] == 'SUSPICIOUS']

    lines.append("## Key Findings")
    lines.append("")

    if fabricated:
        lines.append(f"🚨 **{len(fabricated)} FABRICATED citations detected** - Authors do not match actual papers")
    if invalid_doi:
        lines.append(f"🚫 **{len(invalid_doi)} INVALID DOIs** - Citations reference non-existent papers")
    if suspicious:
        lines.append(f"⚠️ **{len(suspicious)} SUSPICIOUS citations** - Multiple discrepancies found")

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
                         'orange' if status == 'SUSPICIOUS' else \
                         'yellow' if status == 'WARNING' else 'green'
            lines.append(f"![Status](https://img.shields.io/badge/Status-{badge_status}-{badge_color})")
            lines.append("")

            # Claimed information
            lines.extend([
                "**Claimed Information:**",
                "",
                f"- **Title:** {r['claimed']['title']}",
                f"- **Authors:** {', '.join(r['claimed']['authors'][:5])}"
            ])

            if len(r['claimed']['authors']) > 5:
                lines.append(f"  - *(+{len(r['claimed']['authors']) - 5} more authors)*")

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
                    lines.extend([
                        "<details>",
                        "<summary><b>Actual Information (from CrossRef)</b></summary>",
                        "",
                        f"- **Title:** {cf.get('title', 'N/A')}",
                        f"- **Authors:** {', '.join(cf.get('authors', [])[:5])}"
                    ])

                    if len(cf.get('authors', [])) > 5:
                        lines.append(f"  - *(+{len(cf['authors']) - 5} more authors)*")

                    lines.extend([
                        f"- **Year:** {cf.get('year', 'N/A')}",
                        f"- **DOI:** `{cf.get('doi', 'N/A')}`",
                        f"- **Venue:** {cf.get('venue', 'N/A')}",
                        "",
                        "</details>",
                        ""
                    ])

            # Generate and display fix suggestions
            if r['issues']:
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
    for status in ['FABRICATED', 'DOI_INVALID', 'SUSPICIOUS', 'WARNING', 'VERIFIED']:
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
