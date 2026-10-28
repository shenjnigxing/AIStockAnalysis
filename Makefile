.PHONY: test test-api test-root build-web
PYTHON ?= python

test: test-root test-api build-web

test-api:
	$(PYTHON) -c "import os,sys,subprocess; os.environ['DATABASE_URL']='sqlite:///:memory:'; os.environ['PYTHONPATH']='apps/api'; sys.exit(subprocess.call([sys.executable,'-m','pytest','-q','apps/api/tests']))"

test-root:
	$(PYTHON) -m pytest -q tests/unit

build-web:
	npm --prefix apps/web run build
