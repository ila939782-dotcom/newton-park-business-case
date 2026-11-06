"""Expected-value B2B operating model. All inputs are educational assumptions."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COSTS = ('research', 'localization', 'demo', 'management', 'legal',
         'operations', 'promotion', 'lead_generation', 'travel')
MULTIPLIERS = ('lead_multiplier', 'conversion_multiplier', 'price_multiplier',
               'fixed_cost_multiplier')


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


def load_inputs(path=ROOT / 'data/monthly_inputs.csv'):
    with Path(path).open(encoding='utf-8') as handle:
        return [{k: v if k == 'month' else float(v) for k, v in row.items()}
                for row in csv.DictReader(handle)]


def evaluate(inputs, assumptions):
    """Recognize revenue on contract delivery; collect upfront + delayed balance.

    Conversion is applied to each originating lead cohort before a sales lag.
    Fractional contracts represent expected values, not observed transactions.
    Costs are paid when incurred. No opening pipeline or receivables are assumed.
    """
    a = assumptions
    required = set(MULTIPLIERS) | {'sales_lag_months', 'collection_lag_months',
        'upfront_share', 'delivery_cost_per_contract_rub', 'opening_cash_rub'}
    for key in required:
        finite_number(a[key], key)
        if a[key] < 0:
            raise ValueError(f'{key} cannot be negative')
    if a['upfront_share'] > 1:
        raise ValueError('upfront_share must be in [0, 1]')
    for key in ('sales_lag_months', 'collection_lag_months'):
        if int(a[key]) != a[key]:
            raise ValueError(f'{key} must be a whole number of months')
    if not inputs:
        raise ValueError('At least one month is required')
    previous = None
    for row in inputs:
        year, month = map(int, row['month'].split('-'))
        if not 1 <= month <= 12:
            raise ValueError('Invalid calendar month')
        ordinal = year * 12 + month
        if previous is not None and ordinal != previous + 1:
            raise ValueError('Months must be unique, consecutive and ordered')
        previous = ordinal
        for key in ('leads', 'conversion', 'price_rub', *(c + '_rub' for c in COSTS)):
            if finite_number(row[key], key) < 0:
                raise ValueError(f'{key} cannot be negative')
        if row['conversion'] > 1 or row['conversion'] * a['conversion_multiplier'] > 1:
            raise ValueError('Conversion must be in [0, 1]; it is never silently capped')

    sales_lag = int(a['sales_lag_months'])
    collection_lag = int(a['collection_lag_months'])
    cohorts = [r['leads'] * a['lead_multiplier'] * r['conversion'] * a['conversion_multiplier'] for r in inputs]
    revenue = [cohorts[i-sales_lag] * inputs[i-sales_lag]['price_rub'] * a['price_multiplier']
               if i >= sales_lag else 0 for i in range(len(inputs))]
    rows, cumulative_cash, cash = [], 0.0, a['opening_cash_rub']
    for i, row in enumerate(inputs):
        contracts = cohorts[i-sales_lag] if i >= sales_lag else 0
        fixed = sum(row[c + '_rub'] for c in COSTS) * a['fixed_cost_multiplier']
        variable = contracts * a['delivery_cost_per_contract_rub']
        receipts = revenue[i] * a['upfront_share']
        if i >= collection_lag:
            receipts += revenue[i-collection_lag] * (1-a['upfront_share'])
        contribution = revenue[i] - variable
        profit = contribution - fixed
        net_cash = receipts - fixed - variable
        cumulative_cash += net_cash
        cash += net_cash
        rows.append(dict(month=row['month'], leads=row['leads'] * a['lead_multiplier'],
            conversion=row['conversion'] * a['conversion_multiplier'],
            expected_contracts=contracts, revenue_rub=revenue[i], direct_cost_rub=variable,
            contribution_rub=contribution, fixed_cost_rub=fixed, operating_result_rub=profit,
            receipts_rub=receipts, net_cash_rub=net_cash,
            cumulative_cash_rub=cumulative_cash, closing_cash_rub=cash))

    total = lambda key: sum(row[key] for row in rows)
    contracted = total('expected_contracts')
    contribution_per_contract = total('contribution_rub') / contracted if contracted else None
    breakeven = total('fixed_cost_rub') / contribution_per_contract if contribution_per_contract and contribution_per_contract > 0 else None
    leads = total('leads')
    summary = {
        'leads': leads,
        'weighted_cohort_conversion': sum(cohorts) / leads if leads else None,
        'expected_contracts_in_horizon': contracted,
        'expected_contracts_after_horizon': sum(cohorts[len(inputs)-sales_lag:]) if 0 < sales_lag < len(inputs) else sum(cohorts) if sales_lag >= len(inputs) else 0,
        'revenue_rub': total('revenue_rub'),
        'direct_cost_rub': total('direct_cost_rub'),
        'fixed_cost_rub': total('fixed_cost_rub'),
        'operating_result_rub': total('operating_result_rub'),
        'operating_margin': total('operating_result_rub') / total('revenue_rub') if total('revenue_rub') else None,
        'receipts_rub': total('receipts_rub'),
        'closing_receivables_rub': total('revenue_rub') - total('receipts_rub'),
        'net_cash_rub': total('net_cash_rub'),
        'minimum_opening_cash_rub': max(0, -min(0, *(r['cumulative_cash_rub'] for r in rows))),
        'minimum_closing_cash_rub': min(r['closing_cash_rub'] for r in rows),
        'closing_cash_rub': rows[-1]['closing_cash_rub'],
        'breakeven_expected_contracts': breakeven,
        'breakeven_whole_contracts': math.ceil(breakeven) if breakeven is not None else None,
    }
    return rows, summary


def write_csv(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs()
    base = json.loads((ROOT / 'data/assumptions.json').read_text())
    scenarios = json.loads((ROOT / 'data/scenarios.json').read_text())
    summaries = []
    for name, overrides in scenarios.items():
        rows, summary = evaluate(inputs, base | overrides)
        write_csv(output / f'{name}_monthly.csv', rows)
        summaries.append({'scenario': name, **summary})
    write_csv(output / 'scenario_comparison.csv', summaries)
    (output / 'summary.json').write_text(json.dumps(summaries, indent=2, allow_nan=False) + '\n')
    sensitivity = []
    for lag in (0, 1, 2, 3):
        for direct in (0, 90000, 180000, 300000):
            _, result = evaluate(inputs, base | {'sales_lag_months': lag, 'delivery_cost_per_contract_rub': direct})
            sensitivity.append({'sales_lag_months': lag, 'delivery_cost_per_contract_rub': direct,
                'operating_result_rub': result['operating_result_rub'],
                'minimum_opening_cash_rub': result['minimum_opening_cash_rub']})
    write_csv(output / 'sensitivity.csv', sensitivity)
    print(json.dumps(summaries, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'reports')
    run(parser.parse_args().out)
