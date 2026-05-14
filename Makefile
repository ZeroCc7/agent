.PHONY: install run lint clean

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	python scripts/lint-deps.py

clean:
	powershell -Command "Remove-Item -Recurse -Force uploads\*, outputs\* -ErrorAction SilentlyContinue"
