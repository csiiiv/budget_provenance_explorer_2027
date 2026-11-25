"""Reconcile budget changes using integer pesos and the original source rows."""
from collections import defaultdict


def linked_budget_pairs(nep_amounts, house_amounts, house_to_nep):
    """Group multiple House links to the same NEP record before comparing."""
    linked = defaultdict(int)
    for house_id, amount in house_amounts.items():
        nep_id = house_to_nep.get(house_id)
        if nep_id in nep_amounts:
            linked[nep_id] += amount
        else:
            yield 0, amount
    for nep_id, amount in nep_amounts.items():
        yield amount, linked[nep_id]


def summarize_budget_changes(pairs, expected_before, expected_after):
    changes = dict.fromkeys(('insertions', 'removals', 'increases', 'decreases'), 0)
    before_total = after_total = 0
    for before, after in pairs:
        before, after = before or 0, after or 0
        before_total += before
        after_total += after
        if before == after:
            continue
        if not before:
            key = 'insertions'
        elif not after:
            key = 'removals'
        else:
            key = 'increases' if after > before else 'decreases'
        changes[key] += after - before
    if (before_total, after_total) != (expected_before, expected_after):
        raise ValueError(f'Budget changes do not reconcile: {before_total} → {after_total}; '
                         f'expected {expected_before} → {expected_after}')
    return {**changes, 'net': after_total - before_total}
