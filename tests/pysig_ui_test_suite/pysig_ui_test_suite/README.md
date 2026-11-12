# PySig Studio initial feature-test suite

## Files

Copy these into the UI development branch:

```text
tests/ui/
pytest.ini
.github/workflows/ui-ci.yml
```

Merge `requirements-dev-ui.txt` into the existing `requirements-dev.txt`.

## Local setup

```bat
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

If `requirements-dev.txt` has not yet been updated:

```bat
python -m pip install pytest playwright pytest-playwright
python -m playwright install chromium
```

## Commands

All tests:

```bat
python -m pytest -v
```

Studio tests only:

```bat
python -m pytest tests/ui -m ui -v --browser chromium --tb=short
```

Core tests without browser tests:

```bat
python -m pytest -m "not ui" -v
```

Watch the browser while diagnosing a test:

```bat
python -m pytest tests/ui/test_movements.py -m ui -v --headed --browser chromium
```

Record a trace:

```bat
python -m pytest tests/ui -m ui --tracing on --browser chromium
```

The tests copy the repository into a temporary directory, so YAML save/edit tests
do not modify the working tree.

## Branch filter

The workflow currently runs on pushes to:

- `ui-development`
- `ui/**`
- `feature/ui/**`

and on pull requests into `main`. Adjust the branch list if the actual UI branch
uses a different name.

## Initial coverage

- Studio startup and JavaScript errors
- command interface
- Model ribbon tools
- grid and zoom
- Entry/Exit carriageway separation
- arm geometry drag
- Entry-lane signal information
- Exit-lane signal exclusion
- signal group rename and phase reference update
- movement drag creation
- phase overlap editing
- save/reopen round trip
- model/validation API
- model run and lane result loading
