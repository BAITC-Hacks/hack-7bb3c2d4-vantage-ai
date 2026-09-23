"""Acceptance checks against actual outputs; run with unittest discover.

python -m unittest discover -s tests -p 'test_outputs.py' -v
Uses a temporary output folder; does not overwrite the team's out/ files.
"""
import csv
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class OutputAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='moneygraph-acceptance-')
        cls.addClassCleanup(cls.temp.cleanup)
        start = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(ROOT / 'run.py'), '--data', str(ROOT / 'data'),
             '--out', cls.temp.name], cwd=ROOT, capture_output=True, text=True, timeout=300)
        cls.elapsed = time.monotonic() - start
        if result.returncode:
            raise RuntimeError('Pipeline failed:\n' + result.stdout + result.stderr)
        cls.outputs = {}
        for name in ('nodes_roles', 'clusters', 'top_nodes'):
            with (Path(cls.temp.name) / (name + '.csv')).open(newline='') as handle:
                reader = csv.DictReader(handle)
                cls.outputs[name] = (reader.fieldnames, list(reader))
        cls.source = pd.read_parquet(ROOT / 'data/nodes.parquet')
        print(f'\nMeasured pipeline elapsed: {cls.elapsed:.2f}s')

    def test_required_schemas(self):
        expected = {
            'nodes_roles': {'gid', 'role', 'role_score', 'cluster_id', 'priority_score', 'evidence'},
            'clusters': {'cluster_id', 'n_nodes', 'n_seed', 'sum_kzt_internal', 'top_gids', 'hypothesis'},
            'top_nodes': {'rank', 'gid', 'role', 'priority_score', 'why'},
        }
        for name, required in expected.items():
            with self.subTest(file=name):
                self.assertTrue(required <= set(self.outputs[name][0]))

    def test_every_source_node_appears_once(self):
        rows = self.outputs['nodes_roles'][1]
        actual = [int(row['gid']) for row in rows]
        self.assertEqual(len(actual), len(self.source))
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(set(actual), set(self.source.gid))

    def test_roles_scores_and_evidence(self):
        allowed = {'consolidator', 'transit', 'distributor', 'terminal',
                   'coordinator', 'peripheral', 'unclassified'}  # documented extension
        for row in self.outputs['nodes_roles'][1]:
            with self.subTest(gid=row['gid']):
                self.assertIn(row['role'], allowed)
                for column in ('role_score', 'priority_score'):
                    score = float(row[column])
                    self.assertTrue(math.isfinite(score) and 0 <= score <= 1)
                self.assertTrue(row['evidence'].strip())
                self.assertLessEqual(len(row['evidence']), 200)

    def test_cluster_membership_and_counts(self):
        nodes = self.outputs['nodes_roles'][1]
        clusters = self.outputs['clusters'][1]
        ids = [row['cluster_id'] for row in clusters]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {row['cluster_id'] for row in nodes})
        seed_ids = set(self.source.loc[self.source.is_seed, 'gid'])
        for cluster in clusters:
            members = [r for r in nodes if r['cluster_id'] == cluster['cluster_id']]
            self.assertEqual(int(cluster['n_nodes']), len(members))
            self.assertEqual(int(cluster['n_seed']), sum(int(r['gid']) in seed_ids for r in members))

    def test_cluster_hypotheses_are_present(self):
        missing = [r['cluster_id'] for r in self.outputs['clusters'][1] if not r['hypothesis'].strip()]
        self.assertFalse(missing, f'{len(missing)} clusters lack required hypotheses')

    def test_top_list_is_ranked_and_consistent(self):
        top = self.outputs['top_nodes'][1]
        nodes = {r['gid']: r for r in self.outputs['nodes_roles'][1]}
        self.assertGreaterEqual(len(top), 20)
        self.assertEqual(len(top), len({r['gid'] for r in top}))
        self.assertEqual([int(r['rank']) for r in top], list(range(1, len(top) + 1)))
        scores = [float(r['priority_score']) for r in top]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for row in top:
            self.assertIn(row['gid'], nodes)
            self.assertEqual(row['role'], nodes[row['gid']]['role'])
            self.assertEqual(float(row['priority_score']), float(nodes[row['gid']]['priority_score']))
            self.assertTrue(row['why'].strip())

    def test_crawl_boundary_not_labelled_terminal(self):
        edges = pd.read_parquet(ROOT / 'data/edges.parquet')
        boundary = set(self.source.loc[self.source.depth == 4, 'gid']) - set(edges.src)
        for row in self.outputs['nodes_roles'][1]:
            if int(row['gid']) in boundary:
                self.assertNotEqual(row['role'], 'terminal', row['gid'])

    def test_runtime_under_five_minutes(self):
        self.assertLess(self.elapsed, 300)


if __name__ == '__main__':
    unittest.main()
