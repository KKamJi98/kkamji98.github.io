"""Release gates cannot waive authored evidence or the ARC display flag."""
import json
import subprocess

import pytest

import webp_release as w
from pipeline import digest
from release_manifest import staged_requires_verification
from test_native_additions import addition
from test_webp_additions import built_site


@pytest.mark.parametrize('directory', ['.jekyll-cache', '_site'])
def test_ignored_independent_review_is_still_required_in_index(addition, directory):
    s = addition
    (s.root / '.gitignore').write_text('.jekyll-cache\n_site\n')
    old = s.root / s.row['review_file']
    relative = 'docs/diagram-native-additions/' + directory + '/independent-review.json'
    target = s.root / relative
    target.parent.mkdir(parents=True)
    old.rename(target)
    s.row['review_file'] = relative
    s.row['review_sha256'] = digest(target.read_bytes())
    (s.root / 'docs/diagram-native-additions.json').write_text(json.dumps(s.manifest))
    w.convert(s.root, s.stamp_path, s.manifest['base_revision'])
    site = s.root.parent / 'delivery-site'
    built_site(s, site)
    w.seal(s.root, site, s.stamp_path, s.manifest['base_revision'])
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=s.root, text=True).splitlines()
    assert relative not in tracked
    with pytest.raises(ValueError, match='absent from index'):
        w.verify_staged(s.root)
    subprocess.run(['git', 'add', '-f', '--', relative], cwd=s.root, check=True)
    assert w.verify_staged(s.root)['indexed'] is True


@pytest.mark.parametrize('quote', ['', "'", '"'])
@pytest.mark.parametrize('before,after,expected', [
    (None, True, True), (False, True, True), (True, False, True),
    (True, None, True), (None, None, False),
])
def test_display_flag_add_change_remove_triggers_but_ordinary_prose_does_not(addition, before, after, expected, quote):
    s = addition
    path = s.root / s.row['post']
    original = path.read_text()

    def content(flag):
        if flag is None:
            return original
        return original.replace('---\n', '---\n' + quote + 'arc_diagram_fixed_fhd' + quote + ': ' + str(flag).lower() + '\n', 1)

    path.write_text(content(before))
    subprocess.run(['git', 'add', '.'], cwd=s.root, check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-qm', 'TEST display flag baseline'], cwd=s.root, check=True)
    path.write_text(content(after) + ('\nOrdinary prose only.\n' if before is after is None else ''))
    subprocess.run(['git', 'add', '--', s.row['post']], cwd=s.root, check=True)
    assert staged_requires_verification(s.root) is expected
