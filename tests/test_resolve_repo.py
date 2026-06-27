"""Tests for resolve_repo.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import resolve_repo


# ---------------------------------------------------------------------------
# resolve_for_ticket – Specification field matching
# ---------------------------------------------------------------------------


class TestResolveForTicketSpec:
    def test_single_spec_match_by_name(self, sample_ticket, sample_repo_map):
        """Matches single spec when Specification value uniquely names it."""
        # sample_ticket has Specification="FHIR Core (FHIR)" which contains "FHIR Core"
        spec, reason = resolve_repo.resolve_for_ticket(sample_ticket, sample_repo_map)
        assert spec is not None
        assert spec["github"] == "HL7/fhir"
        assert "FHIR Core" in reason

    def test_longest_match_wins_over_shorter_name(self, sample_repo_map):
        """Longest-match tie-break: 'FHIR Core' beats 'US Core' for a value that
        contains both substrings.  The winning reason must mention the longer name."""
        # sv_low = "fhir core us core" contains both "fhir core" (len 9) and
        # "us core" (len 7) as substrings → both specs match, but HL7/fhir has
        # the longer overlap so the tie-breaker picks it and says "longest match".
        ticket = {
            "key": "FHIR-1",
            "fields": {"Specification": "FHIR Core US Core"},
        }
        spec, reason = resolve_repo.resolve_for_ticket(ticket, sample_repo_map)
        assert spec is not None
        assert spec["github"] == "HL7/fhir"
        assert "longest match" in reason

    def test_ambiguous_when_top_matches_truly_tied(self, sample_repo_map):
        """Returns None + ambiguous reason when two specs share the same match length."""
        # Add a second spec whose name also matches at the same length as the first.
        tied_map = dict(sample_repo_map)
        tied_map["specifications"] = list(sample_repo_map["specifications"]) + [
            {
                "names": ["Core IG"],
                "github": "HL7/core-ig",
                "url_patterns": [],
            }
        ]
        # Spec value "Core" is equally contained in "FHIR Core" (overlap=len("core")=4)
        # and in "US Core" (overlap=4) and in "Core IG" (overlap=4) — all tied at 4.
        ticket = {"key": "FHIR-2", "fields": {"Specification": "Core"}}
        spec, reason = resolve_repo.resolve_for_ticket(ticket, tied_map)
        assert spec is None
        assert "ambiguous" in reason.lower()
        assert "tied" in reason.lower()

    def test_us_core_matches_us_core_spec(self, sample_repo_map):
        """A Specification value 'US Core' uniquely resolves to HL7/US-Core."""
        ticket = {"key": "FHIR-3", "fields": {"Specification": "US Core (FHIR)"}}
        spec, reason = resolve_repo.resolve_for_ticket(ticket, sample_repo_map)
        assert spec is not None
        assert spec["github"] == "HL7/US-Core"


# ---------------------------------------------------------------------------
# resolve_for_ticket – URL pattern fallback
# ---------------------------------------------------------------------------


class TestResolveForTicketURL:
    def test_url_fallback_when_spec_is_empty(self, sample_repo_map):
        """Falls back to URL pattern matching when Specification field is empty."""
        ticket = {
            "key": "FHIR-4",
            "fields": {
                "Specification": "",
                "Related URL": "https://build.fhir.org/observation.html",
            },
        }
        spec, reason = resolve_repo.resolve_for_ticket(ticket, sample_repo_map)
        assert spec is not None
        assert spec["github"] == "HL7/fhir"
        assert "URL pattern" in reason

    def test_url_fallback_when_spec_is_absent(self, sample_repo_map):
        """Falls back to URL pattern matching when Specification key is missing."""
        ticket = {
            "key": "FHIR-5",
            "fields": {
                "Related URL": "https://hl7.org/fhir/us/core/StructureDefinition-us-core-patient.html",
            },
        }
        spec, reason = resolve_repo.resolve_for_ticket(ticket, sample_repo_map)
        assert spec is not None
        assert spec["github"] == "HL7/US-Core"

    def test_url_ambiguous_when_multiple_specs_match(self, sample_repo_map):
        """Returns None + error when multiple specs match the same URL."""
        # Add a second spec that also claims the generic hl7.org/fhir/ pattern.
        ambig_map = dict(sample_repo_map)
        ambig_map["specifications"] = list(sample_repo_map["specifications"]) + [
            {
                "names": ["FHIR Clone"],
                "github": "HL7/fhir-clone",
                "url_patterns": [r"^https?://(www\.)?hl7\.org/fhir/"],
            }
        ]
        ticket = {
            "key": "FHIR-6",
            "fields": {
                "Specification": "",
                "Related URL": "https://hl7.org/fhir/observation.html",
            },
        }
        spec, reason = resolve_repo.resolve_for_ticket(ticket, ambig_map)
        assert spec is None
        assert "ambiguous" in reason.lower()
        assert "HL7/fhir" in reason or "HL7/fhir-clone" in reason

    def test_unresolved_when_nothing_matches(self, sample_repo_map):
        """Returns None + unresolved reason when no spec and no URL matches."""
        ticket = {
            "key": "FHIR-7",
            "fields": {
                "Specification": "",
                "Related URL": "https://example.com/totally-unknown",
            },
        }
        spec, reason = resolve_repo.resolve_for_ticket(ticket, sample_repo_map)
        assert spec is None
        assert "no Specification field match" in reason


# ---------------------------------------------------------------------------
# _merge_maps
# ---------------------------------------------------------------------------


class TestMergeMaps:
    def _base(self):
        return {
            "default_clone_root": "/base/root",
            "specifications": [
                {
                    "github": "HL7/fhir",
                    "names": ["FHIR Core"],
                    "default_branch": "master",
                    "url_patterns": [r"hl7\.org/fhir/"],
                }
            ],
        }

    def test_preserves_base_names_when_override_only_sets_local_path(self):
        """Override that only adds local_path does not wipe the base names list."""
        base = self._base()
        over = {
            "specifications": [
                {"github": "HL7/fhir", "local_path": "/my/clone/fhir"}
            ]
        }
        result = resolve_repo._merge_maps(base, over)
        spec = next(s for s in result["specifications"] if s["github"] == "HL7/fhir")
        assert spec["names"] == ["FHIR Core"]
        assert spec["local_path"] == "/my/clone/fhir"

    def test_extends_names_without_duplicates(self):
        """Override adds new names; existing names are not duplicated."""
        base = self._base()
        over = {
            "specifications": [
                {
                    "github": "HL7/fhir",
                    "names": ["FHIR Core", "FHIR Spec Extra"],
                }
            ]
        }
        result = resolve_repo._merge_maps(base, over)
        spec = next(s for s in result["specifications"] if s["github"] == "HL7/fhir")
        assert spec["names"].count("FHIR Core") == 1
        assert "FHIR Spec Extra" in spec["names"]

    def test_overrides_scalar_field_default_branch(self):
        """Override replaces scalar fields like default_branch."""
        base = self._base()
        over = {
            "specifications": [
                {"github": "HL7/fhir", "default_branch": "main"}
            ]
        }
        result = resolve_repo._merge_maps(base, over)
        spec = next(s for s in result["specifications"] if s["github"] == "HL7/fhir")
        assert spec["default_branch"] == "main"

    def test_overrides_default_clone_root(self):
        """Top-level default_clone_root in override replaces the base value."""
        base = self._base()
        over = {"default_clone_root": "/new/root"}
        result = resolve_repo._merge_maps(base, over)
        assert result["default_clone_root"] == "/new/root"

    def test_no_default_clone_root_in_override_keeps_base(self):
        """When override omits default_clone_root the base value is preserved."""
        base = self._base()
        over = {"specifications": []}
        result = resolve_repo._merge_maps(base, over)
        assert result["default_clone_root"] == "/base/root"


# ---------------------------------------------------------------------------
# _normalize_spec_value
# ---------------------------------------------------------------------------


class TestNormalizeSpecValue:
    def test_string_passthrough(self):
        assert resolve_repo._normalize_spec_value("FHIR Core") == "FHIR Core"

    def test_dict_with_value_key(self):
        assert resolve_repo._normalize_spec_value({"value": "US Core"}) == "US Core"

    def test_dict_with_name_key(self):
        assert resolve_repo._normalize_spec_value({"name": "FHIR IG"}) == "FHIR IG"

    def test_list_joined(self):
        result = resolve_repo._normalize_spec_value(["FHIR Core", "US Core"])
        assert result == "FHIR Core US Core"

    def test_none_returns_empty_string(self):
        assert resolve_repo._normalize_spec_value(None) == ""

    def test_list_with_none_entries(self):
        """None entries inside a list are silently dropped."""
        result = resolve_repo._normalize_spec_value([None, "FHIR Core", None])
        assert result == "FHIR Core"


# ---------------------------------------------------------------------------
# _candidate_urls
# ---------------------------------------------------------------------------


class TestCandidateURLs:
    def test_extracts_from_related_url(self):
        ticket = {"fields": {"Related URL": "https://hl7.org/fhir/obs.html"}}
        urls = resolve_repo._candidate_urls(ticket)
        assert "https://hl7.org/fhir/obs.html" in urls

    def test_extracts_from_description_links(self):
        ticket = {
            "fields": {"_description_links": "https://build.fhir.org/ig/HL7/US-Core"},
        }
        urls = resolve_repo._candidate_urls(ticket)
        assert "https://build.fhir.org/ig/HL7/US-Core" in urls

    def test_extracts_from_description(self):
        ticket = {
            "description": "See https://hl7.org/fhir/patient.html for details.",
            "fields": {},
        }
        urls = resolve_repo._candidate_urls(ticket)
        assert "https://hl7.org/fhir/patient.html" in urls

    def test_multiple_sources_combined(self):
        ticket = {
            "fields": {"Related URL": "https://hl7.org/fhir/obs.html"},
            "description": "Also see https://build.fhir.org/ig/HL7/US-Core",
        }
        urls = resolve_repo._candidate_urls(ticket)
        assert any("hl7.org" in u for u in urls)
        assert any("build.fhir.org" in u for u in urls)

    def test_empty_ticket_returns_empty_list(self):
        assert resolve_repo._candidate_urls({}) == []


# ---------------------------------------------------------------------------
# resolve_local_path
# ---------------------------------------------------------------------------


class TestResolveLocalPath:
    def test_uses_explicit_local_path(self):
        """Explicit local_path in spec is returned as-is (expanded)."""
        spec = {"github": "HL7/fhir", "local_path": "/explicit/path/fhir"}
        result = resolve_repo.resolve_local_path(spec, "/ignored/root")
        assert result == Path("/explicit/path/fhir")

    def test_falls_back_to_default_clone_root(self):
        """Without local_path, returns default_clone_root / repo_name."""
        spec = {"github": "HL7/fhir"}
        result = resolve_repo.resolve_local_path(spec, "/tmp/test-hl7")
        assert result == Path("/tmp/test-hl7/fhir")

    def test_falls_back_to_home_dev_hl7_when_no_root(self):
        """Without local_path or default_clone_root, uses ~/dev/hl7/repo_name."""
        spec = {"github": "HL7/US-Core"}
        result = resolve_repo.resolve_local_path(spec, None)
        assert result == Path.home() / "dev" / "hl7" / "US-Core"

    def test_tilde_in_local_path_is_expanded(self):
        """~ in local_path is expanded to the home directory."""
        spec = {"github": "HL7/fhir", "local_path": "~/repos/fhir"}
        result = resolve_repo.resolve_local_path(spec, None)
        assert result == Path.home() / "repos" / "fhir"

    def test_tilde_in_default_clone_root_is_expanded(self):
        """~ in default_clone_root is expanded."""
        spec = {"github": "HL7/fhir"}
        result = resolve_repo.resolve_local_path(spec, "~/dev/hl7")
        assert result == Path.home() / "dev" / "hl7" / "fhir"


# ---------------------------------------------------------------------------
# main – --group mode
# ---------------------------------------------------------------------------


class TestMainGroup:
    def _write_ticket(self, tmp_path: Path, name: str, ticket: dict) -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(ticket))
        return p

    def test_groups_tickets_and_reports_unresolved(
        self, tmp_path, sample_repo_map, monkeypatch
    ):
        """--group groups resolved tickets and lists unresolved ones."""
        fhir_ticket = {
            "key": "FHIR-10",
            "fields": {"Specification": "FHIR Core (FHIR)"},
        }
        unknown_ticket = {
            "key": "FHIR-99",
            "fields": {"Specification": ""},
        }
        p1 = self._write_ticket(tmp_path, "FHIR-10.json", fhir_ticket)
        p2 = self._write_ticket(tmp_path, "FHIR-99.json", unknown_ticket)

        # Write a minimal repo-map.json so load_map() has something to read.
        map_path = tmp_path / "repo-map.json"
        map_path.write_text(json.dumps(sample_repo_map))

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setattr(
            resolve_repo,
            "SHIPPED_MAP_REL",
            "repo-map.json",
        )

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = resolve_repo.main(["--group", f"{p1},{p2}"])

        output = json.loads(buf.getvalue())
        assert "HL7/fhir" in output["groups"]
        assert "FHIR-10" in output["groups"]["HL7/fhir"]
        assert any(u["key"] == "FHIR-99" for u in output["unresolved"])
        assert rc == 3  # non-zero because there are unresolved tickets

    def test_group_handles_corrupt_json_gracefully(
        self, tmp_path, sample_repo_map, monkeypatch
    ):
        """Corrupt ticket JSON is routed to unresolved rather than crashing."""
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("{not valid json!!!")

        map_path = tmp_path / "repo-map.json"
        map_path.write_text(json.dumps(sample_repo_map))

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setattr(resolve_repo, "SHIPPED_MAP_REL", "repo-map.json")

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = resolve_repo.main(["--group", str(corrupt)])

        output = json.loads(buf.getvalue())
        assert len(output["unresolved"]) == 1
        assert "failed to read ticket file" in output["unresolved"][0]["reason"]
        assert rc == 3


# ---------------------------------------------------------------------------
# load_map
# ---------------------------------------------------------------------------


class TestLoadMap:
    def test_raises_file_not_found_when_repo_map_missing(self, tmp_path, monkeypatch):
        """FileNotFoundError is raised when no repo-map.json can be located.

        load_map() has two lookup paths:
          1. plugin_root / SHIPPED_MAP_REL   (controlled via _plugin_root)
          2. Path(__file__).resolve().parent.parent / "repo-map.json"  (hardcoded)

        Path (2) always resolves to the real skill dir which does contain
        repo-map.json, so we must neutralise it by patching Path.exists to
        return False for all paths, while also blocking the override files.
        """
        from unittest.mock import patch

        monkeypatch.setattr(resolve_repo, "USER_MAP", tmp_path / "no-user-map.json")
        monkeypatch.setattr(resolve_repo, "PROJECT_MAP", tmp_path / "no-project-map.json")
        monkeypatch.setattr(resolve_repo, "_plugin_root", lambda: tmp_path)

        # Patch Path.exists globally so neither the shipped path nor the
        # __file__-relative fallback appears to exist.
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                resolve_repo.load_map()

    def test_loads_from_shipped_location(self, tmp_path, sample_repo_map, monkeypatch):
        """load_map() successfully reads from the CLAUDE_PLUGIN_ROOT shipped map."""
        skills_dir = tmp_path / "skills" / "fhir-jira-workflow"
        skills_dir.mkdir(parents=True)
        (skills_dir / "repo-map.json").write_text(json.dumps(sample_repo_map))

        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setattr(resolve_repo, "USER_MAP", tmp_path / "no-user-map.json")
        monkeypatch.setattr(resolve_repo, "PROJECT_MAP", tmp_path / "no-project-map.json")
        monkeypatch.setattr(resolve_repo, "_plugin_root", lambda: tmp_path)

        result = resolve_repo.load_map()
        assert "specifications" in result
        assert result["version"] == 1

    def test_loads_from_codex_plugin_root(self, tmp_path, sample_repo_map, monkeypatch):
        """load_map() successfully reads from the CODEX_PLUGIN_ROOT shipped map."""
        skills_dir = tmp_path / "skills" / "fhir-jira-workflow"
        skills_dir.mkdir(parents=True)
        (skills_dir / "repo-map.json").write_text(json.dumps(sample_repo_map))

        monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
        monkeypatch.setenv("CODEX_PLUGIN_ROOT", str(tmp_path))
        monkeypatch.setattr(resolve_repo, "USER_MAP", tmp_path / "no-user-map.json")
        monkeypatch.setattr(resolve_repo, "PROJECT_MAP", tmp_path / "no-project-map.json")

        result = resolve_repo.load_map()
        assert "specifications" in result
        assert result["version"] == 1
