# Personal local Docker stack

Copy `.env.example` to `.env`, then run `docker compose up --build` from the repository root. The supported local stack is API + Web using SQLite; PostgreSQL and Redis are not started or published when they are not used.

- Host access is loopback only (`127.0.0.1:3000` and `127.0.0.1:8000`). Inside its isolated network the Web process listens on `0.0.0.0` so port forwarding works.
- The API stores data at `/data/aistock.local.sqlite3`, mounted from repository `./data`. Native operator CLI defaults to the same host file; explicit native `DATABASE_URL` overrides must be checked by the operator.
- Run a container-side quote command with `docker compose exec api python -m app.cli.quotes --kind us_equity --symbol AAPL`. This shares the running API configuration and cache. Real provider availability is not guaranteed.
- Frontend installation uses the committed package lock with `npm ci`. No source bind mount replaces container dependencies. `.dockerignore` excludes host dependencies, builds, secrets and databases.
- This remains a personal development/research stack, not an internet deployment. Stop API/collector writers before making a filesystem backup. Startup refuses incompatible existing table structures; back up and migrate explicitly rather than deleting a database to make startup succeed.

Docker is not available in the implementation environment; configuration and regression assertions were checked, but container build/network/volume behavior must also pass the deployment runner.
