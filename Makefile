# Run from repository root. On Windows, use Git Bash or: nmake -f Makefile (if nmake available).

.PHONY: dev backend frontend test lint install-backend install-frontend train-smoke

install-backend:
	cd backend && python -m pip install -r requirements.txt

install-frontend:
	cd frontend && npm ci

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm start

dev:
	@echo "Run backend and frontend in two terminals: make backend   and   make frontend"

test:
	cd backend && python -m pytest tests/ -q
	cd frontend && npm test -- --watchAll=false

train-smoke:
	cd backend && python scripts/setup_real_data.py --generate-sample
	cd backend && python -m pytest tests/unit/test_with_real_data.py -q

lint:
	cd backend && black --check app tests && flake8 app tests --max-line-length=120 --extend-ignore=E203,W503
	cd frontend && npm run lint
