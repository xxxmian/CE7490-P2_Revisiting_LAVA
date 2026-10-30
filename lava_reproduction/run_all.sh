#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -v
python3 run.py --suite validation --workers 4 --output results/validation
python3 run.py --suite sweep --workers 4 --output results/sweep
python3 run.py --suite heldout --workers 4 --output results/heldout
python3 run.py --suite smoke --workers 4 --output results/smoke
python3 scripts/audit_results.py
python3 scripts/build_figures.py
