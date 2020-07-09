dev-env:
	. venv/bin/activate; \
	pip install -r requirements.txt; \
	pip install -e .[tests]

test:
	. venv/bin/activate; \
	pytest tests/unit

format:
	. venv/bin/activate; \
	black src/probflow tests; \
	flake8 src/probflow tests

documentation:
	. venv/bin/activate; \
	sphinx-build -b html docs docs/_html

package:
	. venv/bin/activate; \
	python setup.py sdist bdist_wheel; \
	twine check dist/*

push-package:
	. venv/bin/activate; \
	twine upload dist/*

clean:
	rm -rf .pytest_cache docs/_html build dist src/probflow.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} \+
