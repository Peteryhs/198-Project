"""Fail before training/refitting under solver versions that change coefficients."""
from importlib.metadata import PackageNotFoundError,version
from pathlib import Path
import sys


def check_environment():
    expected=dict(line.strip().split('==') for line in (Path(__file__).with_name('requirements-modelling.txt')).read_text().splitlines() if line.strip() and not line.startswith('#'))
    errors=[]
    if sys.version_info[:2]!=(3,12):errors.append(f'Python 3.12 required, got {sys.version.split()[0]}')
    for name,want in expected.items():
        try:got=version(name)
        except PackageNotFoundError:got='missing'
        if got!=want:errors.append(f'{name}: expected {want}, got {got}')
    if errors:raise RuntimeError('Modelling environment mismatch: '+ '; '.join(errors)+'. Run: uv run --locked python scripts/<script>.py ... (see docs/MODELLING-ENVIRONMENT.md)')
    return expected
