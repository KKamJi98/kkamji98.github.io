"""Every compiler policy dependency must join build seals and staged triggers."""
from pathlib import Path
import subprocess
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

HOST_LOCAL = ['Gemfile.lock', '_posts/2025/12/.DS_Store', 'assets/img/favicons/_site/favicon.ico',
              'assets/img/favicons/.jekyll-cache/Jekyll/entry']

def _snapshot_tree(tmp_path, monkeypatch, ignore):
    manifest = tmp_path / downloads.MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{}')
    monkeypatch.setattr(downloads, 'delivery_output_paths', lambda root, data: set())
    for relative in HOST_LOCAL + ['assets/img/real.png']:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_bytes(relative.encode())
    if ignore:
        subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
        (tmp_path / '.gitignore').write_text('Gemfile.lock\n.DS_Store\n_site\n.jekyll-cache\nassets/img/real.png\n')
    return downloads.source_snapshot(tmp_path)

def test_ignored_host_local_files_do_not_bind_the_seal_to_a_host(tmp_path, monkeypatch):
    snapshot = _snapshot_tree(tmp_path, monkeypatch, ignore=True)
    assert not set(HOST_LOCAL) & set(snapshot)
    assert 'assets/img/real.png' in snapshot

def test_host_local_names_stay_sealed_unless_git_ignores_them(tmp_path, monkeypatch):
    snapshot = _snapshot_tree(tmp_path, monkeypatch, ignore=False)
    assert set(HOST_LOCAL) | {'assets/img/real.png'} <= set(snapshot)
