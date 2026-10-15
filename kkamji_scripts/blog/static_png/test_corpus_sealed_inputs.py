"""Every compiler policy dependency must join build seals and staged triggers."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'kkamji_scripts/blog/static_png'))
import downloads
import release_manifest

POLICIES = ['corpus_clearance.py', 'corpus_flow_balance.py', 'corpus_typography.py', 'corpus_pod_identity.py', 'corpus_relation_clearance.py']

@pytest.mark.parametrize('name', POLICIES)
def test_compiler_policy_dependency_enters_source_snapshot(tmp_path, monkeypatch, name):
    manifest = tmp_path / downloads.MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{}')
    monkeypatch.setattr(downloads, 'delivery_output_paths', lambda root, data: set())
    relative = 'kkamji_scripts/blog/' + name
    policy = tmp_path / relative
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text('VALUE = 24\n')
    first = downloads.source_snapshot(tmp_path)
    assert relative in first
    policy.write_text('VALUE = 32\n')
    second = downloads.source_snapshot(tmp_path)
    assert first[relative] != second[relative]

@pytest.mark.parametrize('name', POLICIES)
def test_staged_compiler_policy_dependency_requires_verification(monkeypatch, name):
    relative = 'kkamji_scripts/blog/' + name
    monkeypatch.setattr(release_manifest.subprocess, 'check_output', lambda *a, **k: relative + '\n')
    assert release_manifest.staged_requires_verification(ROOT)

def test_unrelated_authoring_script_does_not_add_a_render_gate(monkeypatch):
    monkeypatch.setattr(release_manifest.subprocess, 'check_output', lambda *a, **k: 'kkamji_scripts/blog/audit_humanizer.py\n')
    assert not release_manifest.staged_requires_verification(ROOT)
