---
name: verify
description: E2E verification of the app after a change in core/ or ui/ — starts the real app, walks the affected pages with the browser, and quantitatively checks that there are no new exceptions in the app log or the terminal. Run ONLY as the last step before ./harness/close.sh (if the task requires it) or when the user explicitly asks to verify — NEVER in init.sh or at session start. Tests and check_contracts.py do NOT replace this step.
---

# Verifying the app end to end

> **Adapt to the project:** replace `<app start command>` and `<app log file>` with the
> real values (e.g. `streamlit run ui/home.py` and `logs/app.log`) the first time you
> adopt the harness.

The tests in `tests/` and `harness/check_contracts.py` do not exercise the real UI:
there are bugs that only show up **using the app**. This skill codifies that manual
test as reproducible, quantitative checks. The more quantitative the check, the
better you self-verify: every step below has a measurable success criterion, not an
impression.

## When it runs (and when NOT)

There are only **two** valid triggers:

1. **Session close:** as the last step before `./harness/close.sh`, when the task is
   completed and its `description` in `harness/feature_list.json` states
   `E2E verification: yes` (or has `UI:` criteria in `acceptance`).
2. **Direct user invocation:** only if they ask to verify explicitly and
   unambiguously ("verify the app", "run /verify", "check the UI end to end").
   A generic mention of "checking" or "reviewing" the code does NOT count.

**NEVER** run it at session start, inside `./harness/init.sh`, or as prior
exploration: it is the most token-expensive skill in the harness and its value lies
in verifying the change ALREADY made, not the starting state.

It does not apply to changes that only touch `harness/`, `tests/` or docs (there
`./harness/init.sh` is enough), nor to tasks whose `description` says
`E2E verification: no` (small changes with no new UI flow). If the task touches
`core/` or `ui/` and its `description` says nothing, apply the default criterion:
run it.

## Choosing the browser (in this order)

1. **Integrated browser** (Claude desktop app): `mcp__Claude_Browser__*` tools
   (`preview_start`, `read_page`, `computer`, …). **It is the preferred way**: it
   starts the app from `.claude/launch.json`, manages the process and gives access
   to server logs (`preview_logs`) and the browser console
   (`read_console_messages`) with no extra work.
2. **Real Chrome** (`mcp__claude-in-chrome__*`, load them via ToolSearch in ONE call
   if deferred): only if the integrated browser is not available. In this case start
   the app yourself with Bash (see the step 2 variant).
3. **No browser**: if the UI renders over a websocket (e.g. Streamlit), a `curl` to
   the port only returns the HTML shell and does NOT count as content verification.
   Leave an explicit note that the visual verification is pending on the user (do
   not claim it done).

## Procedure

### 1. Log baseline

```bash
BASE_LOG=$(wc -l < <app log file> 2>/dev/null || echo 0)
```

### 2. Start the real app

**With the integrated browser (preferred):** `preview_start` — it uses the
`.claude/launch.json` configuration and opens the tab by itself. Save the `serverId`
(for `preview_logs`/`preview_stop`) and the `tabId` from the result. If the app was
already running, `preview_start` reuses the server: reload the page to start from a
clean state. Do NOT start the app with Bash on this path.

**Fallback with real Chrome:** launch it with Bash in the background
(`run_in_background: true`):

```bash
<app start command>   # on a free port dedicated to verification
```

and wait until the output indicates the server is ready. If the port is busy, use
another one.

**Criterion (both paths):** it starts without a traceback in <30s — check it with
`preview_logs` (level `error`) or the background process output.

### 3. Walk the pages with the browser

With the chosen browser, open the app and walk:

1. **The main page**: it renders without an exception message.
2. **The page/tab affected by the session's change** — this is the important step:
   **interact with the changed flow, do not just look at it**. If the change was a
   button/form, press/fill it and check the resulting state (did the expected data
   file change? does the row show the new value?); if it was a computation, verify a
   concrete value against the source data.
3. A quick pass over the remaining pages to detect collateral breakage: each one
   loads without a visible exception.

Tips with the integrated browser: to verify text and structure prefer `read_page`
(returns refs for `computer`/`form_input`) over screenshots; use `computer` for
clicks/keyboard and `read_console_messages` with `onlyErrors: true` to catch
frontend JS errors.

Take a **screenshot** of the affected page as evidence (`screenshot` action of
`computer` on either path).

Caution: if the pages trigger external API calls, it is normal for them to take a
while; an external network failure is NOT a failure of the change (check it in the
log: those paths must log a warning and degrade without breaking).

### 4. Check logs and output

```bash
tail -n +$((BASE_LOG + 1)) <app log file> | grep -nE "ERROR|Traceback" || echo "no new errors"
```

**Criterion:** zero new `ERROR`/`Traceback` lines attributable to the change (a
documented external network warning does not count). Also review the app process
output: with the integrated browser, `preview_logs` with `level: "error"`; with Bash
in the background, the process output. Zero tracebacks.

### 5. Stop the app

With the integrated browser: `preview_stop` with the `serverId`. With Bash: kill the
process launched in step 2. Do not leave hanging processes.

## Result

Report as a list of checks with their measured result (startup OK, page X renders,
interaction Y produces Z, 0 new errors in the log), not as "everything works". If
any check fails, the feature is NOT ready for `done` or for `./harness/close.sh`.
