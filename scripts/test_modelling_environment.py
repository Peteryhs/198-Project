"""Pin agreement and fail-fast regression, without downloading a mismatched environment."""
import tomllib
from pathlib import Path
from unittest.mock import patch
import modelling_environment as env

def main():
    pins=env.check_environment()
    root=Path(__file__).resolve().parents[1]
    project=tomllib.loads((root/'pyproject.toml').read_text())
    assert dict(x.split('==') for x in project['project']['dependencies'])==pins
    lock=tomllib.loads((root/'uv.lock').read_text())
    locked={x['name']:x['version'] for x in lock['package']}
    assert all(locked[k]==v for k,v in pins.items())
    with patch.object(env,'version',return_value='0.0.0'):
        try:env.check_environment()
        except RuntimeError as e:assert 'uv run --locked' in str(e) and 'scikit-learn' in str(e)
        else:raise AssertionError('version drift accepted')
    print('Python 3.12; requirements/project/lock agree:',pins)
    print('mismatched installed versions fail before fitting with repair command')
if __name__=='__main__':main()
