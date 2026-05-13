"""Shared fixtures for fhir-jira-toolkit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add the scripts directory to sys.path so tests can import directly
SCRIPTS_DIR = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "fhir-jira"
    / "skills"
    / "fhir-jira-workflow"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def sample_ticket():
    """Minimal valid ticket dict as produced by fetch_ticket.py."""
    return {
        "key": "FHIR-12345",
        "url": "https://jira.hl7.org/browse/FHIR-12345",
        "summary": "Add example for Quantity with SI unit",
        "status": "Closed",
        "resolution": "Persuasive",
        "issuetype": "Change Request",
        "description": "The spec should include an example of Quantity with SI units.",
        "fields": {
            "Specification": "FHIR Core (FHIR)",
            "Related URL": "https://hl7.org/fhir/observation.html",
            "Resolution Description": "Add an example showing SI-derived units.",
        },
        "fetched_at": "2026-05-12T16:00:00Z",
    }


@pytest.fixture
def sample_repo_map():
    """Minimal repo map with two specs for resolution testing."""
    return {
        "version": 1,
        "default_clone_root": "/tmp/test-hl7",
        "specifications": [
            {
                "names": ["FHIR Core", "FHIR Specification"],
                "github": "HL7/fhir",
                "default_branch": "master",
                "publisher": "./gradlew publish",
                "qa_path": "output/qa.json",
                "build_dirs": ["output", "temp", "build", ".gradle"],
                "url_patterns": [
                    r"^https?://(www\.)?hl7\.org/fhir/(?!us/|uv/)",
                    r"^https?://build\.fhir\.org/(?!ig/)",
                ],
            },
            {
                "names": ["US Core"],
                "github": "HL7/US-Core",
                "default_branch": "master",
                "publisher": "./_updatePublisher.sh && ./_genonce.sh",
                "qa_path": "output/qa.json",
                "build_dirs": ["output", "temp", "input-cache"],
                "url_patterns": [
                    r"hl7\.org/fhir/us/core/",
                    r"build\.fhir\.org/ig/HL7/US-Core",
                ],
            },
        ],
    }


@pytest.fixture
def qa_schema_variants():
    """Dict of the 4 QA JSON schema shapes the parser handles."""
    return {
        "newer_top_level": {
            "errs": 3,
            "warnings": 10,
            "hints": 5,
            "links": 1,
        },
        "older_top_level": {
            "errors": 3,
            "warnings": 10,
            "info": 5,
            "brokenlinks": 1,
        },
        "summary_subobject": {
            "summary": {
                "errors": 3,
                "warnings": 10,
                "info": 5,
                "brokenlinks": 1,
            }
        },
        "per_file_messages": {
            "files": [
                {
                    "messages": [
                        {"level": "error"},
                        {"level": "error"},
                        {"level": "fatal"},
                        {"level": "warning"},
                        {"level": "warning"},
                        {"level": "information"},
                        {"level": "hint"},
                        {"level": "broken-link"},
                    ]
                }
            ]
        },
    }
