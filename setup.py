#!/usr/bin/env python3
"""
Setup script for Citation DOI Validator

Install with:
    pip install .

Or for development:
    pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / 'README.md'
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ''

setup(
    name='citation-doi-validator',
    version='1.0.0',
    description='Academic citation verification tool for BibTeX files',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Lalit Narayan Mishra, Amit Rangari, Sandesh Nagrare, Saroj Kumar Nayak',
    author_email='lnm8910@gmail.com',
    url='https://github.com/lnm8910/citation-doi-validator',
    license='MIT',
    py_modules=['citation_validator'],
    python_requires='>=3.8',
    install_requires=[
        'requests>=2.28.0',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'citation-validator=citation_validator:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',
        'Topic :: Text Processing :: Markup :: LaTeX',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='citation verification DOI CrossRef BibTeX academic-integrity peer-review',
)
