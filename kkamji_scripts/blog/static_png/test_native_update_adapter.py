"""Integration boundaries between native deltas and WebP/index evidence."""
import json
from pathlib import Path

from test_native_update import delta
from downloads import source_snapshot, webp_url
from pipeline import digest
import webp_release as w


def test_overlay_changes_only_named_output_and_keeps_original_png_archive(delta):
    s = delta
    original = (s.root / s.row['old_png'][1:]).read_bytes()
    native = w.checked_native(s.root, s.old, s.manifest['base_revision'])
    assert s.row['new_png'] in native['rows'] and s.row['old_png'] not in native['rows']
    assert len(native['rows']) == len(s.baseline['entries']) + len(s.baseline['unused_entries'])
    assert native['archive_inputs'][s.row['old_png'][1:]] == digest(original)
    assert (s.root / s.row['old_png'][1:]).read_bytes() == original
    assert native['baseline'] == s.baseline and native['stamp'] == s.old


def test_update_png_and_webp_are_outputs_not_source_fingerprint_inputs(delta):
    s = delta
    before = source_snapshot(s.root)
    assert s.row['new_png'][1:] not in before
    webp = s.root / webp_url(s.row['new_png'])[1:]
    webp.write_bytes(w.encode_lossless((s.root / s.row['new_png'][1:]).read_bytes()))
    assert source_snapshot(s.root) == before


def test_update_manifest_is_bound_to_delivery_source_fingerprint(delta):
    s = delta
    before = source_snapshot(s.root)
    path = s.root / 'docs/diagram-native-update.json'
    path.write_bytes(path.read_bytes() + b'\n')
    assert source_snapshot(s.root) != before
