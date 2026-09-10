# swarm-harness

Run many agents at once, each with its **own tab**, all sharing **one logged-in Chrome**.

Each swarm agent runs under its own `BU_NAME` (`swarm-<id>`) so it gets its own
daemon + socket (true parallelism), but every agent binds to the **same** browser
via `BU_CDP_URL` (default the `:9333` agent Chrome). One browser means every tab
shares the same logged-in session, so every agent acts as you.

Built for ~2-5 concurrent agents. It scales past that, bounded by the host Chrome.

## Commands

```bash
swarm-harness up            # preflight: make sure the shared :9333 Chrome is up
swarm-harness <id> <<'PY'   # run an agent under its own tab (id: [A-Za-z0-9_-])
swarm-harness ctl <<'PY'    # control ops: swarm_status(), swarm_reap()
swarm-harness down          # reap all agents, stop ctl, clear the runtime dir
```

Reserved ids: `up`, `ctl`, `down`. Any other id is an agent.

## Per-agent pattern

Every agent calls `swarm_open()` first to claim its own tab, then uses any core
helper (`page_info`, `click_at_xy`, `js`, `goto_url`, ...) which now drives that
tab only:

```bash
swarm-harness scrape1 <<'PY'
swarm_open("https://x.com/home")
wait_for_load()
print(page_info())
# ... work ...
swarm_close()          # optional; `swarm-harness down` also cleans up
PY
```

`swarm_open()` force-creates a fresh CDP target each call, so two agents starting
at the same instant can never land on the same tab.

## Fan out (the actual swarm)

Drive it from a bash loop or from parallel sub-agents. Each invocation is fully
isolated, so just launch them concurrently:

```bash
for id in a b c d; do
  ( swarm-harness "$id" <<PY >"/tmp/swarm-$id.out" 2>&1
swarm_open("https://example.com/?who=$id")
print(page_info())
PY
  ) &
done
wait
```

From this Claude harness: give each Agent-tool sub-agent one `swarm-harness <id>`
invocation. They run in true parallel against the shared browser.

## Manage the fleet

```bash
swarm-harness ctl <<'PY'
import json
print(json.dumps(swarm_status(), indent=2))   # [{agent, name, alive, url, title}]
print(swarm_reap())                            # close every agent tab + stop daemons
PY
```

`swarm_reap()` closes each tab through its **own** agent daemon, so it only
touches agent-owned tabs, never your own tabs in the shared browser.

## Env overrides

| Var | Default | Purpose |
|-----|---------|---------|
| `BH_SWARM_CDP` | inherit `BU_CDP_URL`, else `http://127.0.0.1:9333` | Point the swarm at a different browser (e.g. a VPS `ws://` endpoint) with no code change |
| `BH_SWARM_PORT` | `9333` | Port `swarm-harness up` probes/launches |
| `BH_SWARM_PROFILE` | `~/ChromeAgent` | Chrome `--user-data-dir` that `up` launches |

## Auth note

The swarm acts as you only on sites the `:9333` Chrome is **logged into**. That
Chrome is signed out of Google by design (local-only agent profile), so log the
target sites into it once (persists in `~/ChromeAgent`). Cloning your Google
session programmatically is fragile and not attempted.

Because all agents share one browser, they are the **same** logged-in you. Agents
logged into **different** accounts would need separate profiles/instances, not
tabs.

## How isolation is enforced

- `BU_NAME=swarm-<id>` -> own daemon + socket (parallel, no shared "current tab").
- `BU_CDP_URL` pinned -> bypasses the name-agnostic local-Chrome auto-discovery
  that otherwise makes every local daemon fight over one browser.
- per-agent `BH_TMP_DIR` -> no shared `shot.png` / debug-overlay collisions.
- shared `BH_RUNTIME_DIR` (`/tmp/bh-swarm-<devid>/runtime`) -> `ctl` can discover
  and reap the whole fleet.
- CDP mode (not local mode) -> the `chrome://inspect` permission flow and its
  shared `inspect-opened` marker are skipped entirely.

Zero edits to core (`admin.py` / `daemon.py` / `_ipc.py`). All logic lives in
`swarm-harness` + `agent-workspace/agent_helpers.py`, so it can't break the
normal single-browser harness.

## Per-account agents (`bh-swarm-as`)

Plain `swarm-harness` binds the whole fleet to ONE browser, so every agent acts as the
same account. To run agents as *different* accounts, go through the identity router:

```bash
bh-swarm-as aggr scrape1 <<'PY'
swarm_open("https://reddit.com/r/selfhelp"); wait_for_load()
PY
```

It resolves the identity from `~/.claude/browsers/identities.json`, points `BH_SWARM_CDP`
at that identity's port, and asserts the live logged-in account before running anything.
Verified 2026-08-26 with two agents on two accounts concurrently (`aggr` =
u/Aggressive-Turn-2987, `adekunes` = u/Adekunes).

Never hand-set `BU_CDP_URL` to switch accounts: browser-harness keys its daemon by
`BU_NAME`, so an already-running daemon ignores the override and silently drives the
wrong account. A PreToolUse hook blocks that pattern.

## Symlink fix (2026-08-26)

`swarm-harness` is normally invoked through `~/.local/bin/swarm-harness`. `ROOT` came from
a bare `dirname "${BASH_SOURCE[0]}"`, which resolved to `~/.local/bin` rather than the repo,
so the `uv` fallback ran in a directory with no package and every call died with
`No module named 'browser_harness'`. `ROOT` now resolves symlinks first.
