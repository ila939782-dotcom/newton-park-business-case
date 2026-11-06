import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from model import evaluate, load_inputs


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.inputs = load_inputs()
        self.base = json.loads((ROOT / 'data/assumptions.json').read_text())

    def test_original_arithmetic_reconciles(self):
        _, s = evaluate(self.inputs, self.base | {'sales_lag_months': 0, 'delivery_cost_per_contract_rub': 0})
        self.assertAlmostEqual(s['revenue_rub'], 15900000)
        self.assertAlmostEqual(s['fixed_cost_rub'], 12060000)
        self.assertAlmostEqual(s['operating_result_rub'], 3840000)
        self.assertAlmostEqual(s['weighted_cohort_conversion'], 13.25 / 114)

    def test_base_independent_control(self):
        _, s = evaluate(self.inputs, self.base)
        self.assertAlmostEqual(s['expected_contracts_in_horizon'], 11)
        self.assertAlmostEqual(s['expected_contracts_after_horizon'], 2.25)
        self.assertAlmostEqual(s['revenue_rub'], 13200000)
        self.assertAlmostEqual(s['operating_result_rub'], -840000)
        self.assertEqual(s['breakeven_whole_contracts'], 12)

    def test_cash_receivables_bridge_every_scenario(self):
        scenarios = json.loads((ROOT / 'data/scenarios.json').read_text())
        for overrides in scenarios.values():
            a = self.base | overrides
            rows, s = evaluate(self.inputs, a)
            self.assertAlmostEqual(s['operating_result_rub'] - s['closing_receivables_rub'], s['net_cash_rub'])
            self.assertAlmostEqual(a['opening_cash_rub'] + s['net_cash_rub'], s['closing_cash_rub'])
            self.assertAlmostEqual(sum(r['expected_contracts'] for r in rows) + s['expected_contracts_after_horizon'], sum(r['leads'] * r['conversion'] for r in rows))

    def test_lags_zero_and_beyond_horizon(self):
        _, s = evaluate(self.inputs, self.base | {'collection_lag_months': 0})
        self.assertAlmostEqual(s['closing_receivables_rub'], 0)
        _, s = evaluate(self.inputs, self.base | {'sales_lag_months': 20})
        self.assertEqual(s['revenue_rub'], 0)
        self.assertAlmostEqual(s['expected_contracts_after_horizon'], 13.25)

    def test_zero_demand_and_unprofitable_unit_economics(self):
        _, s = evaluate(self.inputs, self.base | {'lead_multiplier': 0})
        self.assertIsNone(s['weighted_cohort_conversion'])
        self.assertIsNone(s['breakeven_whole_contracts'])
        _, s = evaluate(self.inputs, self.base | {'delivery_cost_per_contract_rub': 1300000})
        self.assertIsNone(s['breakeven_whole_contracts'])

    def test_invalid_inputs_rejected(self):
        for override in ({'upfront_share': 1.1}, {'conversion_multiplier': 10}, {'sales_lag_months': 1.5}, {'price_multiplier': float('nan')}, {'opening_cash_rub': -1}):
            with self.assertRaises(ValueError):
                evaluate(self.inputs, self.base | override)
        bad = copy.deepcopy(self.inputs)
        bad[1]['month'] = bad[0]['month']
        with self.assertRaises(ValueError):
            evaluate(bad, self.base)


if __name__ == '__main__':
    unittest.main()
