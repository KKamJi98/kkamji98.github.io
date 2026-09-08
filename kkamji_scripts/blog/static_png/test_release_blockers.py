"""Source topology regressions for release blockers B2 and B3."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]


def fragment(path):
    return ET.fromstring((ROOT / '_includes/diagrams/static' / path).read_text())


def has_class(element, name):
    return name in element.get('class', '').split()


class ReleaseBlockerSources(unittest.TestCase):
    def test_rollback_is_conditional_and_exposure_is_not_a_next_hop(self):
        fig = fragment('sap-c02/deployment-rollback-paths.html')
        lanes = [e for e in fig.iter('section') if has_class(e, 'sd-lane')]
        self.assertEqual(len(lanes), 4)
        for lane in lanes:
            self.assertFalse(any(has_class(e, 'sd-arrow') for e in lane.iter()))
            fields = {e.get('data-attribute'): e for e in lane.iter() if e.get('data-attribute')}
            self.assertEqual(set(fields), {'deployment', 'rollback', 'exposure'})
            self.assertIn('실패 시', ''.join(fields['rollback'].itertext()))
            self.assertIn('노출', ''.join(fields['exposure'].itertext()))

    def test_vault_cross_boundary_edges_have_owned_endpoints(self):
        fig = fragment('ci-cd/ci-cd-study/vault-secrets-operator.html')
        edges = {e.get('data-relation'): e for e in fig.iter() if e.get('data-relation')}
        self.assertEqual(set(edges), {'controller-vault', 'pod-a-database', 'pod-b-cloud'})
        self.assertTrue(has_class(edges['controller-vault'], 'sd-arrow--both'))
        for relation, edge in edges.items():
            source = next(e for e in fig.iter() if e.get('id') == edge.get('data-from'))
            target = next(e for e in fig.iter() if e.get('id') == edge.get('data-to'))
            self.assertTrue(any(source in list(e.iter()) and e.get('data-boundary') == 'kubernetes' for e in fig.iter()))
            self.assertTrue(any(target in list(e.iter()) and e.get('data-boundary') == 'external' for e in fig.iter()))
            parent = next(p for p in fig.iter() if edge in list(p))
            siblings = list(parent)
            self.assertIn(target, list(siblings[siblings.index(edge) + 1].iter()))
            self.assertTrue(''.join(edge.itertext()).strip(), relation)
        for element in fig.iter():
            if element.get('data-boundary') == 'kubernetes':
                labels = [''.join(e.itertext()) for e in element.iter() if has_class(e, 'sd-label')]
                self.assertFalse(set(labels) & {'Vault API', 'Database', 'Cloud'})
        text = ''.join(fig.itertext())
        for actor in ['Vault Secrets Operator Controller', 'Application Pod A', 'Application Pod B']:
            self.assertEqual(text.count(actor), 1, actor)


if __name__ == '__main__':
    unittest.main()
