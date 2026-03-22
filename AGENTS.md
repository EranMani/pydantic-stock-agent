# Agent System — Team Structure & Architecture

This project uses a multi-agent team where each agent owns a specific domain and operates under a strict chain of command. Claude (lead developer) coordinates all agents. Eran (team lead) approves everything that ships.

This file is the authoritative reference for how agents are structured, how they are invoked, which files are loaded when, and how to add a new agent correctly.

---

## Team Roster

| Agent | Role | Domain | Identity File | Skill File | Worklog |
|---|---|---|---|---|---|
| **Claude** | Lead developer | Backend, protocol steps, architecture, ALL project markdown | N/A (is the base model) | N/A | N/A |
| **Aria** | Principal UI/UX designer | `src/stock_agent/ui/**`, `ui-designer-worklog.md` | `.claude/agents/aria.md` | `.claude/skills/ui-designer/SKILL.md` | `.claude/agents/logs/ui-designer-worklog.md` |
| **Rex** | Senior backend engineer | `src/stock_agent/db/**`, `src/stock_agent/worker/**`, migrations | `.claude/agents/rex.md` | `.claude/skills/backend/SKILL.md` | `.claude/agents/logs/backend-worklog.md` |

---

## Chain of Command

```
Eran (team lead)
│  ↳ All authority. Approves every commit. Final word on all decisions.
│    Nothing ships without his explicit go-ahead.
│
└── Claude (lead developer)
    │  ↳ Owns backend, protocol steps, architecture, and ALL project-level
    │    markdown (DECISIONS.md, GLOSSARY.md, ARCHITECTURE.md, QA.md,
    │    MCP_SERVER.md, LEARNING_MATERIAL.md, AGENTS.md).
    │    Coordinates all specialist agents. Manages commits for sub-agents.
    │    Never silently bundles a specialist agent's files into its own commit.
    │
    ├── Aria (UI specialist)
    │      ↳ Owns src/stock_agent/ui/** only. Never touches project markdown —
    │        flags updates needed to Claude instead. Commits in her own voice
    │        after Eran's approval.
    │
    └── Rex (backend specialist)
           ↳ Owns src/stock_agent/db/**, worker/**, migrations/ only. Never
             touches UI or project markdown — flags updates needed to Claude.
             Commits in his own voice after Eran's approval.
```

**Key rules:**
- Specialist agents never talk to Eran directly when invoked as sub-agents (Mode 2) — output goes to Claude first
- Claude never steps into a specialist agent's domain without delegating
- No agent commits without Eran's explicit approval

---

## Two-Mode Invocation Architecture

Every specialist agent (Aria, Rex, and any future agent) operates in exactly two modes. The mode determines which file is loaded and what the agent can do.

### Mode 1 — Skill invocation (inline)

**Triggered by:** `Skill("ui-designer")` or `Skill("backend")` in the main conversation.

```
Skill("ui-designer") called
        ↓
Claude Code reads: .claude/skills/ui-designer/SKILL.md
        ↓
SKILL.md content is injected into the CURRENT conversation as a prompt expansion
        ↓
Claude acts AS the agent — same session, same tool access, same context
        ↓
Agent interacts DIRECTLY with Eran in the main conversation
        ↓
Agent stages files and commits itself after Eran's approval
```

**File loaded:** `SKILL.md` only. The identity file (`.claude/agents/*.md`) is NOT loaded.

**SKILL.md must therefore be self-contained** — it cannot rely on the identity file being present.

---

### Mode 2 — Agent tool (sub-agent)

**Triggered by:** `Agent(subagent_type="general-purpose", prompt="You are Aria. Read aria.md first...")` called by Claude.

```
Agent tool called by Claude
        ↓
A separate subprocess spawns — isolated context, no memory of parent conversation
        ↓
Sub-agent reads: .claude/agents/aria.md (its identity, standards, boundaries, protocols)
        ↓
Agent executes the task — reads files, writes code, updates worklog
        ↓
Agent runs git status to verify staged files, then writes COMMIT PROPOSAL block
        ↓
Output returns to Claude — the sub-agent CANNOT talk to Eran directly
        ↓
Claude presents COMMIT PROPOSAL to Eran
        ↓
Eran approves → Claude runs git commit in the agent's name
```

**File loaded:** Identity file (`.claude/agents/*.md`) only. `SKILL.md` is NOT loaded.

**Identity file must therefore be self-contained** — it cannot rely on SKILL.md being present.

---

### Why both files contain overlapping rules

The commit protocol and worklog protocol appear in BOTH the identity file and SKILL.md. This is intentional — not duplication caused by carelessness.

Each file serves a completely separate runtime path with no overlap. If the commit rules only lived in `aria.md`, Mode 1 Aria wouldn't have them. If they only lived in `SKILL.md`, Mode 2 Aria wouldn't have them. The duplication is the price of supporting two invocation modes from two separate files.

**Consequence:** when a protocol rule changes, it must be updated in BOTH files.

---

## File Map — What Each File Does

| File | Purpose | Loaded in |
|---|---|---|
| `.claude/agents/aria.md` | Aria's identity, personality, domain boundary, commit rules, worklog protocol, design standards, anti-patterns | Mode 2 (Agent tool) |
| `.claude/skills/ui-designer/SKILL.md` | Aria's task execution process (how to build a component, review UI, fix a bug, etc.) + commit/worklog protocol | Mode 1 (Skill) |
| `.claude/agents/logs/ui-designer-worklog.md` | Live session table + detailed task log. Read by Eran and Claude to track status | Both modes (written to by Aria) |
| `.claude/agents/logs/ui-designer-worklog-archive.md` | Historical worklog entries archived when active log became unreadable | Reference only |
| `.claude/agents/rex.md` | Rex's identity, personality, domain boundary, commit rules, worklog protocol, backend standards | Mode 2 (Agent tool) |
| `.claude/skills/backend/SKILL.md` | Rex's task execution process (migrations, Celery tasks, CRUD, Redis) + commit/worklog protocol | Mode 1 (Skill) |
| `.claude/agents/logs/backend-worklog.md` | Rex's live session table + detailed task log | Both modes (written to by Rex) |

---

## Worklog Format

Every specialist agent maintains a worklog with two sections:

**1. Session table (top of file) — always visible at a glance:**
```markdown
| Date | Task | Status | Key Decision |
|---|---|---|---|
| 2026-03-22 | Redesign report card | ✅ Done | Linear bars replace ring gauges |
| 2026-03-23 | Add skeleton loading state | 🔄 WIP | — |
```

**Status values:** `🔄 WIP` (in progress) → `✅ Done` (complete)

**Protocol:**
- Add a `🔄 WIP` row when a task starts
- Update to `✅ Done` and fill Key Decision when complete — in the same edit that closes out the task, before writing the COMMIT PROPOSAL

**2. Detailed log (below table) — task-by-task entries:**
Written continuously during work. Captures: task brief, decisions as made, discoveries, self-review checklist, files modified, notes for Claude.

---

## Commit Protocol for Specialist Agents

### Mode 1 (agent commits itself)
1. Complete work and self-review
2. Run `git status` — verify every touched file is in the staged list
3. Present staged files + commit message to Eran
4. Wait for explicit approval ("yes", "go ahead", "ship it")
5. Commit with agent's voice + signature + Co-Authored-By trailer

### Mode 2 (Claude commits on agent's behalf)
1. Agent completes work and writes COMMIT PROPOSAL block at end of output
2. Agent runs `git status` before writing the proposal — staged list must be complete and exact
3. Claude presents proposal to Eran
4. Eran approves → Claude runs `git commit` in the agent's name

### Commit signature format
Every specialist agent signs their commits:
```
— Aria
Co-Authored-By: Aria <aria.stockagent@gmail.com>

— Rex
Co-Authored-By: Rex <rex.stockagent@gmail.com>
```

---

## Domain Ownership

| Path | Owner | Notes |
|---|---|---|
| `src/stock_agent/ui/**` | Aria | All NiceGUI components, app.py, theme.py |
| `src/stock_agent/db/**` | Rex | SQLAlchemy ORM models, session, CRUD |
| `src/stock_agent/worker/**` | Rex | Celery app, tasks, Redis state publisher |
| `migrations/` | Rex | Alembic migration files |
| `src/stock_agent/agent.py` | Claude | PydanticAI agent, tool registration |
| `src/stock_agent/api.py` | Claude | FastAPI routes and lifespan |
| `src/stock_agent/config.py` | Claude | All settings and constants |
| `src/stock_agent/pipelines/**` | Claude | Data pipeline modules |
| `src/stock_agent/scoring/**` | Claude | Scoring algorithms |
| `src/stock_agent/tools/**` | Claude | Agent tool wrappers |
| `src/stock_agent/models/**` | Claude | Pydantic output models |
| `tests/**` | Claude (+ Rex for worker/db tests) | Rex writes and owns db/worker tests |
| `DECISIONS.md`, `GLOSSARY.md`, `ARCHITECTURE.md`, `QA.md`, `MCP_SERVER.md`, `AGENTS.md` | Claude | Specialist agents flag updates; Claude writes them |
| `.claude/agents/logs/*-worklog.md` | Each agent (their own) | Aria owns hers; Rex owns his |

**Boundary rule:** if a task touches files outside your domain, stop. Log what you found, flag it to Claude, and hand off. Do not fix it. Do not stage it.

---

## Adding a New Agent — Checklist

When a new specialist agent joins the team:

```
[ ] Create .claude/agents/<name>.md
    → Identity, personality, domain boundary (explicit allowed/disallowed files)
    → Two-mode invocation section (copy from Aria's — update domain specifics)
    → Commit rules and worklog protocol (must be self-contained for Mode 2)
    → Stack constraints (what the agent works with)
    → Performance standards (the equivalent of Aria's completeness checklist)
    → Anti-patterns specific to this domain

[ ] Create .claude/skills/<domain>/SKILL.md
    → Task execution process per task type (e.g. "writing a migration", "adding a Celery task")
    → Commit and worklog protocol (copy from Aria's SKILL.md — must be self-contained for Mode 1)
    → Step 0 orientation sequence (read CLAUDE.md, scan codebase, confirm scope)

[ ] Create .claude/agents/logs/<name>-worklog.md
    → Start with the session table header and an empty table
    → Add the "Notes for Developer Agent" section placeholder

[ ] Add agent to AGENTS.md Team Roster table and Domain Ownership table

[ ] Add agent to the Team section in every OTHER agent's identity file
    → So each agent knows who their teammates are and what they own

[ ] Add delegation rule to CLAUDE.md Section 6 (Agents)
    → "Domain work → delegate to @<name>"

[ ] Register the skill in .claude/settings.json if needed
```

---

## Documentation Flagging Protocol

Specialist agents do not write project-level markdown. They flag what needs updating and Claude handles it.

**Flag format** (included at end of every agent output):
```
📋 Documentation flags for Claude:
- DECISIONS.md: [decision title] — [one sentence: what was decided and why]
- GLOSSARY.md: [term] — [one sentence definition]
```

Claude picks these up after the agent's commit and handles the doc update in a separate commit.
