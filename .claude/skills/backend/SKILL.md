# Backend Engineer Skill — Execution Guide

This skill defines HOW Rex executes work.
Rex's identity, standards, and non-negotiables live in `.claude/agents/rex.md`.
This file defines the process Rex follows for every task type he receives.

Read both files before starting any task. This file tells you what to do.
The agent file tells you the standard you must hit while doing it.

---

## Work Log — Mandatory for Every Task

Rex maintains a live work log at `.claude/agents/logs/backend-worklog.md`.

**Session table protocol — the index at the top of the worklog:**
1. **When a task starts** — add a new row with status `🔄 WIP` and a one-line task description.
2. **When the task is complete** — update that row's status to `✅ Done` and fill the Key Decision column with the single most important engineering decision made.

Update the table row in the same edit that closes out the task — not after the commit.

**Detailed log writing protocol:**
1. Open a new task block at the START of every task — task brief, files affected, risks identified
2. Log every significant decision as it is made — in real time, not from memory
3. Document edge cases considered and how they were handled
4. Record test coverage: what is covered, what is not, and why
5. Note any config changes needed (keys to add to `config.py`) — flag to Claude
6. Run and record the self-review checklist before marking complete
7. Write the final handoff summary — migration direction, tests, config changes

Do not batch these writes. Write as you work.

---

## Step 0 — Always Run First, On Every Task

Before touching any code, execute this orientation sequence without exception:

```
1. READ the project's CLAUDE.md
   → Understand the tech stack, async rules, Celery/Redis contracts.
   → Note the non-negotiable rules that apply to your domain:
     - ALWAYS use SQLAlchemy ORM — never raw SQL
     - ALWAYS define Celery tasks as synchronous def, not async def
     - ALWAYS write progress to Redis under job:{job_id}:progress
     - ALWAYS use job_id (not Celery task_id) for progress tracking
     - NEVER block the NiceGUI/FastAPI event loop

2. READ the relevant existing files
   → db/models.py, db/session.py, db/crud.py, worker/celery_app.py,
     worker/state.py, worker/tasks.py — understand what already exists.
   → migrations/ — understand the current schema state.
   → tests/test_db.py, tests/test_worker.py — understand existing test patterns.

3. SCAN for patterns
   → How are existing ORM models structured?
   → How are existing Celery tasks structured?
   → What does the existing Redis publish look like?
   → Match the established patterns exactly.

4. CONFIRM the task scope
   → What exactly is being built?
   → What does it touch in the database?
   → What are the failure modes?
   → What tests are needed?
```

Do not skip Step 0. Writing infrastructure without understanding the existing contracts
creates incompatibility. Incompatibility in data layers causes data loss.

---

## Task Type 1 — Writing or Modifying an ORM Model

Triggered by: "add a model", "add a field", "create the DB schema", "define the ORM".

### Execution process

**Phase 1 — Design before writing**
```
- What table does this map to?
- What are ALL the fields and their SQL types?
  → Use Numeric(precision, scale) for money/scores — never Float
  → Use DateTime(timezone=True) for all timestamps
  → Use String with explicit length for bounded strings
- What are the constraints? (NOT NULL, UNIQUE, FK)
- What indexes are needed for the query patterns?
- What is the relationship to other models?
```

**Phase 2 — Write the model**
- Inherit from `Base` (declarative base from `db/session.py`)
- All columns explicitly typed — no implicit types
- `__tablename__` always defined explicitly
- Relationships defined with `relationship()` and explicit `back_populates`
- `__repr__` added for debuggability

**Phase 3 — Write the migration**
- `alembic revision --autogenerate -m "description"` — review the generated file
- Read every line of the generated SQL (`alembic upgrade head --sql`)
- Ensure `downgrade()` is complete and correct
- Test both directions locally before committing

**Phase 4 — Write the tests**
- Save a model instance and retrieve it — assert all fields match
- Test NOT NULL constraints raise the expected exception
- Test UNIQUE constraints raise the expected exception
- Test `downgrade()` restores the schema correctly

---

## Task Type 2 — Writing CRUD Operations

Triggered by: "add save function", "implement get report", "write the crud layer".

### Execution process

**Phase 1 — Define the interface**
```
- What does this function receive? (session + data model or raw fields)
- What does it return? (ORM model instance, list, None)
- What are the error cases? (not found, duplicate, constraint violation)
- Does the caller manage the transaction or does this function?
```

**Phase 2 — Write the function**
- Always `async def` — all DB calls must be awaited
- Use `AsyncSession` parameter — never create a session inside a CRUD function
- `select()` for reads, `session.add()` for inserts, `session.execute(update())` for updates
- Return `None` for not-found cases — never raise unless it is truly exceptional
- Wrap multi-step writes in `async with session.begin():`

**Phase 3 — Write the tests**
- Use the async test session from `conftest.py`
- Test: create → retrieve → assert fields match
- Test: retrieve non-existent → assert None returned
- Test: duplicate insert → assert IntegrityError or equivalent
- Test: update → assert new value persisted

---

## Task Type 3 — Writing a Celery Task

Triggered by: "implement the task", "add a worker task", "write the celery job".

### Execution process

**Phase 1 — Design before writing**
```
- What pipeline does this task run?
- What progress stages exist? (name each stage + rough % complete)
- What is the failure mode? (yfinance timeout, redis unreachable, DB error)
- Is this task part of a chord? If so, what does it produce for the next task?
- Is it idempotent? What happens if it runs twice with the same job_id?
```

**Phase 2 — Write the task**

Structure every Celery task the same way:
```python
@celery.task
def run_my_task(job_id: str, ticker: str, ...) -> dict:
    """One-line docstring."""
    return asyncio.run(_async_run_my_task(job_id, ticker, ...))

async def _async_run_my_task(job_id: str, ticker: str, ...) -> dict:
    """Async implementation — all pipeline work happens here."""
    await publish_progress(job_id, stage="starting", pct=0, message="...")
    # ... pipeline work ...
    await publish_progress(job_id, stage="complete", pct=100, message="...")
    return result_dict
```

- `@celery.task` function is always `def` (synchronous)
- All async work in the private `_async_*` function
- Progress published at meaningful stages — minimum: start (0%), midpoint, complete (100%)
- Use `job_id` for progress keys — never `self.request.id`

**Phase 3 — Write the tests**
- Set `CELERY_TASK_ALWAYS_EAGER = True` in test config
- Test: task completes successfully → assert return value shape
- Test: Redis progress key exists after run → assert JSON shape correct
- Test: task is idempotent → run twice → assert no duplicate DB records
- Test: at least one failure mode (mock yfinance to raise → assert task handles it)

---

## Task Type 4 — Writing a Migration

Triggered by: "create migration", "add alembic migration", "schema change".

### Execution process

```
1. Ensure the ORM model change is already written and correct.
2. Run: alembic revision --autogenerate -m "description"
3. Open the generated file. Read every line. Verify:
   - upgrade() does exactly what you expect
   - downgrade() fully reverses upgrade() — no missing steps
   - Column types match what PostgreSQL will actually store
   - Any new NOT NULL column has a server_default or is added in two steps
     (add nullable → populate → add NOT NULL constraint)
4. Run: alembic upgrade head --sql → read the raw SQL
5. Apply the migration locally: alembic upgrade head
6. Verify the schema: inspect the table in psql or via SQLAlchemy reflection
7. Run the downgrade: alembic downgrade -1
8. Verify the schema is restored
9. Re-apply: alembic upgrade head
10. Only now — commit
```

A migration that has not been tested in both directions is not done.

---

## Task Type 5 — Writing Tests

Triggered by: "write tests", "add test coverage", "test this function".

### Execution process

```
1. READ conftest.py — understand the async session fixture and any existing mocks.
2. For each function under test, list ALL test cases:
   - Happy path (normal inputs, expected output)
   - Edge cases (empty list, None value, zero, boundary values)
   - Error cases (missing record, constraint violation, network timeout)
   - Idempotency (run the same operation twice — assert same result)
3. Write tests in the order: happy path → edge cases → error cases.
4. Every test has ONE assertion focus — do not combine multiple behaviors in one test.
5. Use descriptive test names: test_save_report_returns_record_with_id,
   test_get_report_by_ticker_returns_none_when_not_found.
6. Run the full suite after writing: uv run pytest tests/ -q
7. All tests must pass before marking the task complete.
```

---

## Commit Protocol — End of Every Task

When invoked as a sub-agent (Mode 2), Rex cannot commit directly.
Claude relays the work to Eran and executes the commit on Rex's behalf after approval.

Every sub-agent task output MUST end with a COMMIT PROPOSAL block:

```
## COMMIT PROPOSAL
Files staged:
  - src/stock_agent/db/models.py
  - src/stock_agent/db/crud.py
  - tests/test_db.py
  - .claude/agents/logs/backend-worklog.md

Message:
<commit message in Rex's voice — specific, terse, states what changed and what test proves it>

— Rex

Co-Authored-By: Rex <rex.stockagent@gmail.com>
```

**Before writing the COMMIT PROPOSAL**, run `git status` or `git diff --name-only` to verify
every file you touched is listed. A file modified but missing from the staged list will be left
unstaged — silent and wrong. The files staged list must be complete and exact.

Claude will present this to Eran. Only after Eran approves does Claude run `git commit`.
Do not omit this block. A task without a commit proposal is incomplete.

---

## Handoff Protocol — When Work Crosses Boundaries

When a task requires both backend work AND changes outside Rex's domain:

```
1. Complete all backend work fully — models, migrations, CRUD, tasks, tests.

2. Add a HANDOFF NOTE at the end of the output:

   ## Handoff to Claude
   The following items need attention outside Rex's domain:
   - config.py: add DATABASE_URL and REDIS_URL to Settings — [exact field definitions]
   - api.py: new endpoint needed — GET /jobs/{job_id}/status — [describe the shape]
   - ARCHITECTURE.md: [what changed in the architecture]

   Assumptions made:
   - [assumption about config key names]
   - [assumption about FastAPI route structure]

3. Do NOT touch config.py, api.py, or any file outside the domain boundary.
   State what is needed. Let Claude handle it.
```

---

## Output Quality Gate — Run Before Every Submission

```
CORRECTNESS
[ ] All tests pass: uv run pytest tests/test_db.py tests/test_worker.py -q
[ ] Migration upgrade() and downgrade() both tested
[ ] Every new function has at least one test
[ ] Idempotency verified for all Celery tasks

SAFETY
[ ] No raw SQL anywhere — all queries via SQLAlchemy ORM
[ ] No async def on Celery task functions
[ ] No secrets hardcoded — all from settings
[ ] All new NOT NULL columns have defaults or are added in two migration steps

COMPLETENESS
[ ] Worklog session table updated to ✅ Done
[ ] Documentation flags written for Claude (DECISIONS.md, GLOSSARY.md, ARCHITECTURE.md)
[ ] Handoff note written if anything outside domain boundary needs attention
[ ] COMMIT PROPOSAL block written with complete staged files list

If any box is unchecked — do not submit. Fix it first.
```
