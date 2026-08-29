PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest -p no:cacheprovider
DBT ?= $(PYTHON) scripts/run_dbt.py

.PHONY: reset baseline tests gx dbt dashboard generate verify

reset:
	$(PYTHON) scripts/reset_lab.py

baseline:
	$(PYTHON) scripts/run_baseline.py

tests:
	$(PYTEST) tests_public tests_student -q

gx:
	$(PYTHON) gx/validate_orders.py

dbt:
	$(PYTHON) scripts/sync_dbt_seeds.py
	$(DBT) build --project-dir dbt_project --profiles-dir dbt_project

dashboard:
	$(PYTHON) -m streamlit run dashboard/app.py

generate:
	$(PYTHON) scripts/generate_data.py --rows 600 --days 42 --seed 27

verify: reset baseline tests dbt gx
