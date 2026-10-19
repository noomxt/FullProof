import unittest
from copy import deepcopy
from verification_v11 import sort_conflicts


class ConflictSortTests(unittest.TestCase):
    def item(self, claim=None, proof=None, field='target_id', reason='MISMATCH'):
        return dict(field=field, reason_code=reason, claim_value=claim, proof_value=proof)

    def test_null_empty_and_strings(self):
        rows = [self.item(v) for v in ['B', '', None, 'A']]
        original = deepcopy(rows)
        self.assertEqual([r['claim_value'] for r in sort_conflicts(rows)], [None, '', 'A', 'B'])
        self.assertEqual(rows, original)

    def test_all_four_sort_keys(self):
        expected = [self.item('B', 'B', 'a', 'A'), self.item('A', 'B', 'a', 'B'),
                    self.item(None, 'B'), self.item('', 'B'),
                    self.item('A', None), self.item('A', ''), self.item('A', 'A'), self.item('A', 'B')]
        self.assertEqual(sort_conflicts(list(reversed(expected))), expected)

    def test_invalid_value_types(self):
        for value in [0, 1.5, True, False, {}, [], ['A']]:
            for name in ['claim_value', 'proof_value']:
                with self.subTest(value=value, name=name):
                    row = self.item()
                    row[name] = value
                    with self.assertRaisesRegex(ValueError, 'INVALID_CONFLICT_VALUE_TYPE'):
                        sort_conflicts([row])

    def test_invalid_structure(self):
        for row in [None, {}, self.item(field=None), self.item(reason=1)]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                sort_conflicts([row])


if __name__ == '__main__':
    unittest.main()
