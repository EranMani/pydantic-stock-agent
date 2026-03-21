# UI Designer — Work Log

> This file is maintained by the ui-designer agent.
> It is written to continuously during work — not just at the end.
> Other agents and the team lead read this to understand current status,
> design decisions, and what work is waiting for them.
> Never delete previous entries. Append only. Most recent session at top.

---

<!-- ============================================================
     COPY THIS BLOCK FOR EVERY NEW TASK. FILL IN AS YOU WORK.
     ============================================================ -->

## [TASK TITLE] — [DATE] [TIME]

### Status
`IN PROGRESS` | `BLOCKED` | `AWAITING HANDOFF` | `COMPLETE`

---

### Task Brief
> What was I asked to do? (1-3 sentences, in my own words — not copy-pasted from the request)

---

### Thinking & Assessment
> My honest analysis before I started building. What did I notice? What concerned me?
> What questions did I have? What assumptions did I make and why?

**Initial observations:**
-

**Concerns flagged before starting:**
-

**Assumptions made (and why):**
-

**Design direction chosen:**
> Why this direction over alternatives? What would I have done differently with more time?

---

### Work In Progress
> Updated in real time as I work. Each meaningful step gets a line.
> This is not a summary — it is a running log written WHILE working.

- [ ] Step / decision / action taken
- [ ] Step / decision / action taken

---

### Design Decisions Log
> Every significant design choice — documented with reasoning.
> If someone asks "why did you do it that way?" the answer is here.

| Decision | Options Considered | Chosen | Reason |
|----------|-------------------|--------|--------|
| | | | |

---

### Discoveries & Issues Found
> Things I found during the work that weren't in the original task.
> Bugs, inconsistencies, existing problems, missing tokens, accessibility failures.

**Found during work:**
-

**Severity:** `Critical` | `High` | `Medium` | `Low`
**Action taken:** Fixed inline | Flagged for later | Needs separate ticket

---

### Open Questions
> Things I don't know that affect this work.
> Each question has my best current answer — I don't leave blanks.

| Question | My Current Answer | Confidence | Needs Input From |
|----------|------------------|------------|-----------------|
| | | High/Med/Low | |

---

### Notes for Developer Agent
> Everything the developer needs to implement or integrate this work correctly.
> Written as if the developer is reading this cold — no assumed context.

**What I built:**
-

**Implementation requirements:**
-

**Data/state dependencies I assumed:**
> List every piece of data this UI needs, what shape I assumed it would be in,
> and where I assumed it would come from.

```
Component: [name]
Needs: [data field] — assumed type: [string/number/array/etc]
Source assumed: [API endpoint / store / prop / context]
Edge case handled: [what I did when this data is null/empty/error]
```

**Tokens I created or modified:**
> If I added new tokens to the token file, list them here so the developer
> knows the token file was changed and needs to be committed.

-

**Files I created or modified:**
-

**Integration notes:**
> Any specific instructions for how to wire this up, import it, or use it.

---

### Self-Review Results
> The completion checklist from the agent file — run before marking complete.
> Every item must be checked. If something is unchecked, explain why and when it will be done.

**Visual completeness**
- [ ] All interactive states designed
- [ ] All data states handled
- [ ] Responsive behavior defined
- [ ] Dark mode handled
- [ ] Long content tested
- [ ] Missing/broken content handled

**Quality completeness**
- [ ] All contrast ratios verified
- [ ] Keyboard navigation complete
- [ ] Focus states designed
- [ ] Touch targets 44px minimum
- [ ] Zero hardcoded values
- [ ] Spacing on 8px grid
- [ ] Typography on defined scale

**Code completeness**
- [ ] CSS clean and co-located
- [ ] No magic numbers
- [ ] ARIA attributes complete
- [ ] Tested with realistic content

**Unchecked items (explain):**
-

---

### Final Status & Handoff
> Written when work is complete or being handed off.

**Outcome:** `Complete and ready to implement` | `Partially complete — see notes` | `Blocked — needs input`

**Handed off to:** `Developer Agent` | `Team Lead` | `Waiting`

**Handoff summary:**
> 3-5 sentences. What did I build? What does the developer need to do with it?
> What decisions might need revisiting once real data flows in?

---
<!-- END OF TASK BLOCK -->
