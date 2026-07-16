# AGENTS.md

## Runtime and checks

- The repository has two applications: Flask/PostgreSQL at the root and a Next.js app in `frontend/`. Start the backend with `python run.py`; it listens on port 5000. Start the frontend with `cd frontend && npm run dev`.
- Install frontend dependencies from the lockfile with `cd frontend && npm ci`. Run `npm run lint` and `npm run build` for frontend verification; the build is also the available TypeScript check.
- The only checked-in test is `pytest tests/test_commission.py`.
- Run `python audit.py` after changing Flask blueprint prefixes or routes; several blueprints specify a local prefix and are also registered with one.
- `requirements.txt` declares the current runtime, migration, and test dependencies. Update it whenever adding a third-party import.

## Backend constraints

- Root `.env` is loaded in `app/__init__.py` before Flask imports. Preserve that order. Importing `app.db` validates database credentials plus `SECRET_KEY` and `JWT_SECRET`; `DB_PORT` defaults to 5432.
- Keep new HTTP handlers in focused blueprints and register them in `app/__init__.py::create_app()`. `app/routes/main.py` is a legacy mix of Jinja admin pages and APIs.
- Keep the layering routes -> services -> `app.db.get_cursor()`. Always use `with get_cursor() as cur:`: it owns commits, rollbacks, pooled connections, and returns `RealDictCursor` dictionaries.
- Flask-Login session cookies authenticate both the legacy Jinja UI and Next.js. JSON routes use `login_required_api` / `admin_required_api`; `main.py`'s `admin_required` redirects for HTML pages. JWT helpers are not request authentication.
- Preserve bcrypt verification with the Werkzeug legacy fallback when changing passwords.
- Use `Decimal` for new monetary or commission calculations. `distribute_commission()` is the commission entrypoint and its per-package rules plus purchase reference provide payout/idempotency behavior.

## Frontend and data operations

- `frontend/src/services/api.js` deliberately calls `http://127.0.0.1:5000/api` with credentials; do not substitute `localhost`. The Next rewrite in `frontend/next.config.mjs` also defaults to `127.0.0.1:5000` and can be changed with `BACKEND_URL`.
- Yoyo migration files live in `migrations/`; inspect `yoyo.ini` before applying them because it includes a concrete local PostgreSQL connection URL.

## Details from Human peer

### for llm

> consider you are a seasoned 35 years+ veteran of website + webapp + cloud domain design.
> pay heed to my advice but be critical of it and correct me when you think I am incorrect.
> Think of me as you assistant with my human inputs.
> We first need to identify and run the current code base. then enhance it and upgrade it. We'll first be running locally on this m/c and m/c of other peer devs.
> The dev m/c and faily low powered linux computers.
> After understanding the current code in it's entireity and before making any significant changes I want you to break our efforts down using github issues. I have github-cli installed.

#### m/c info

my personal dev m/c info can be found out using btop etc..
it's arch linux based m/c x86 ultra series cpus.
get more m/c info using various linux commands.

### functional

1. MLM platform (multi-level marketing)
2. both website + post-login webapp for members.
3. members could be admin or mlm members at various tier.
4. the website needs to host the product catalogue.
5. the webapp needs to have the product info/catalogue and user specific info and role.
6. fix the commision logic ask for any clarification if needed.
7. user info and privelages: commision | mlm hierarcy etc.

### non-functional

- [] a website with product catalogue and a login option for mlm members that allows access to memembers only functionality.
- [] it should be production grade and scalable to support around 100000 members and the website should be able to handle a daily traffic of 100K visitors (both members and non-members)
- [] use microservice arhitecture if needed for scaling
- [] use postgrest and have a good schema to support website info/ users/members info, security creds, comission info and other persistant info.
- [] We'll migrate to cloud for production deployments

## initial

- [] Create a `feature/mvp` branch in the sibling worktree `/home/quomptrade/Work/learn/mlm-sarvesh-feature-mvp`; make all MVP changes there and merge it to `main` only after MVP completion.

- [] Critique the code and tech-stack used. identify the risks ahead.
- [] Add github workflow and contribution guidelines.
- [] Identify scope of work and create github issues. We are targetting 30 days to prod release with moderate daily updates.
- [] Also include documentation of the code in markdown possibly also integrate some documentation hosting like doxygen etc..
- [] add docs and readme for better peer documentation/understanding.
- [] add documentation gen tools like sphynx/doxygen etc whatever suitable.
- [] fix .gitignore and add agentic dev files/tools.
- [] add dir with requirements for the project. use git-lfs to store large bin files.

## task lists

### basic sanity fixes (once we have a local instance running with schema we need to add github issues with priorities)

- [] add automation testing suite for integration and unit testing for both UI and BE modules.
- [] compare flask vs python fast api and migratee to it if need be.
- [] design and implement good communication setup for inter service communication
- [] fix build/test cycle. add unit test and integration test to both python backend/flask code and frontend next.js code.
- [] Make this production ready

## stated goal

> Have a professional (institutional grade) MLM website/web-platform.

## Milestone and Issue Breakdown Plan

MVP (minimum viable product) P0 tasks.
P0 tasks would be one instance of the smallest unit of implementation for 1 particular module to constitute our MVP.
Later on peer modules could be onboarded as part of p1 and p2 issues.
for ex. registration feature with gmail registration should be p0 and we can onboard username / twitter based registration and multi-login modes later on as part of p1 and p2 issues.

Milestones:

1. MVP Staging ( 1 week) all P0 issues
2. MVP cloud migration and production roleout (2 days depending cloud infra availability) otherwise resort to local deployement and testing.
3. Enhance v1 release to production (aditional 1 week) P1/P2 issues.

## dev workflow notes

> [!NOTE]

1. make one commit per issue use commit message format [github issue id] <brief summary> + description
2. make small atomic issue and small atomic commits.
