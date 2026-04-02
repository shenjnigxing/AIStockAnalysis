.PHONY: test test-api test-root build-web

test: test-root test-api build-web

test-api:
	cd apps/api && "D:/Users/sjx/Anaconda/envs/py311/python.exe" -m pytest -q

test-root:
	"D:/Users/sjx/Anaconda/envs/py311/python.exe" -m pytest -q

build-web:
	cd apps/web && npm run build
