"""Agent-editable browser helpers.

Add task-specific browser primitives here. Core helpers from browser_harness.helpers
load this file when BH_AGENT_WORKSPACE points at this directory, or when this
repo's default agent-workspace exists.

--------------------------------------------------------------------------------
SWARM HELPERS
--------------------------------------------------------------------------------
Run many agents at once, each with its OWN tab, all sharing ONE logged-in Chrome.

Model: every swarm agent runs under its own BU_NAME (`swarm-<id>`) via the
`swarm-harness` wrapper, so it gets its own daemon + socket (true parallelism)
but binds to the SAME browser through BU_CDP_URL (default the :9333 agent
Chrome). Because it is one browser, every tab shares the same logged-in session.

Per agent:
    swarm-harness 1 <<'PY'
    swarm_open("https://x.com/home")   # fresh, dedicated tab pinned to this agent
    print(page_info())                 # every core helper now drives ONLY this tab
    PY

Control (run once, id `ctl`):
    swarm-harness ctl <<'PY'
    print(swarm_status())   # who is alive, what tab each drives
    print(swarm_reap())     # close every agent tab + stop every agent daemon
    PY

Bring the shared browser up (pure preflight, no daemon needed):
    swarm-harness up

Isolation is enforced by the wrapper (per-agent BU_NAME + BH_TMP_DIR, shared
BH_RUNTIME_DIR so control ops can discover every agent). These helpers only need
to (a) hand each agent its own tab and (b) let the ctl process manage the fleet.
"""

# All imports are done lazily inside functions: this module is exec'd while
# browser_harness.helpers is still mid-import (it calls _load_agent_helpers() at
# the bottom of its own module load), so importing sibling modules at top level
# would risk a partially-initialized-module surprise. At call time everything is
# fully loaded.


def swarm_open(url="about:blank"):
    """Create a fresh, dedicated tab for THIS agent and pin the daemon to it.

    Force-creates a new CDP target every call instead of reusing a blank tab, so
    two agents connecting at the same moment can never land on the same tab
    (new_tab()'s blank-tab reuse path would let them). Returns the tab handle
    dict ({targetId, url, title}). After this, page_info(), click_at_xy(), js(),
    goto_url(), etc. all act on this tab only.
    """
    from browser_harness.helpers import cdp, switch_tab, goto_url, current_tab
    tid = cdp("Target.createTarget", url="about:blank")["targetId"]
    switch_tab(tid)  # attach this daemon's session to the new target (+marks title)
    if url and url != "about:blank":
        goto_url(url)
    return current_tab()


def swarm_close():
    """Close this agent's current tab. Optional: swarm_reap() also cleans up."""
    from browser_harness.helpers import close_tab
    try:
        close_tab()
        return True
    except Exception:
        return False


def _swarm_ipc(name, req, timeout=5.0):
    """One request to the daemon named `name` over its own socket. For talking to
    OTHER swarm daemons (ctl -> agents) since BU_NAME is fixed per process."""
    from browser_harness import _ipc as ipc
    c, token = ipc.connect(name, timeout=timeout)
    try:
        return ipc.request(c, token, req)
    finally:
        try:
            c.close()
        except OSError:
            pass


def _swarm_names(include_ctl=False):
    """Live `swarm-*` daemon names in the shared runtime dir (self excluded)."""
    from browser_harness.admin import _daemon_endpoint_names
    from browser_harness.helpers import NAME
    names = [n for n in _daemon_endpoint_names() if n.startswith("swarm-")]
    if not include_ctl:
        names = [n for n in names if not n.endswith("-ctl")]
    return [n for n in names if n != NAME]


def swarm_status():
    """List live swarm agent daemons and the tab each is driving.

    Returns a list of {agent, name, alive, url, title}, one per agent daemon.
    """
    from browser_harness.admin import _daemon_browser_connection
    out = []
    for n in _swarm_names(include_ctl=True):
        conn = _daemon_browser_connection(n)
        page = (conn or {}).get("page") or {}
        out.append({
            "agent": n[len("swarm-"):],
            "name": n,
            "alive": conn is not None,
            "url": page.get("url", ""),
            "title": page.get("title", ""),
        })
    return out


def swarm_reap(close_tabs=True):
    """Stop every swarm agent daemon and (optionally) close its tab.

    Runs from the ctl process; never reaps itself. Each tab is closed through its
    OWN agent daemon, so only agent-owned tabs are touched, never your own tabs
    in the shared browser. Returns {"reaped": [names]}.
    """
    from browser_harness.admin import restart_daemon
    reaped = []
    for n in _swarm_names(include_ctl=False):
        if close_tabs:
            try:
                cur = _swarm_ipc(n, {"meta": "current_tab"})
                tid = cur.get("targetId") if isinstance(cur, dict) else None
                if tid:
                    _swarm_ipc(n, {"method": "Target.closeTarget",
                                   "params": {"targetId": tid}, "session_id": None})
            except Exception:
                pass
        try:
            restart_daemon(n)  # stops the daemon + cleans its socket/pid
            reaped.append(n)
        except Exception:
            pass
    return {"reaped": reaped}
