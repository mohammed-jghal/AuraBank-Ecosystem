PYTHON ?= python3

.PHONY: install data measure test quality run docker

install:
	$(PYTHON) -m pip install -r requirements.txt

data:
	$(PYTHON) scripts/generate_data.py

measure: data
	$(PYTHON) scripts/measure.py

test:
	$(PYTHON) run_tests.py

quality:
	$(PYTHON) -m compileall -q src tests scripts run_app.py run_tests.py

run:
	$(PYTHON) run_app.py

docker:
	docker build -t aurabank-poc .
