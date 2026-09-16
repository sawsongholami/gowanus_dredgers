"""
Runs every data loader in sequence. Each loader is idempotent (upserts on
its primary key), so re-running this any time is safe.

    python main.py

A loader that fails (e.g. a sheet not shared yet, a site being down)
prints its error and the rest still run; the summary at the end says
which succeeded.
"""

import traceback

import cwqt
import duro
import observations
import turbidity_rta1
import turbidity_rta2

LOADERS = [
    ('Duro sonde readings -> duro', duro),
    ('CWQT Enterococcus -> cwqt', cwqt),
    ('RTA2 turbidity PDFs -> turbidity_rta2', turbidity_rta2),
    ('GRT_Reports sheet -> turbidity_rta1', turbidity_rta1),
    ('Observation survey -> observations', observations),
]


def main():
    results = {}
    for label, module in LOADERS:
        print(f'\n=== {label} ===')
        try:
            module.main()
            results[label] = 'ok'
        except Exception as exc:
            traceback.print_exc()
            results[label] = f'FAILED: {exc}'

    print('\n=== Summary ===')
    for label, outcome in results.items():
        print(f'  {label}: {outcome}')


if __name__ == '__main__':
    main()
