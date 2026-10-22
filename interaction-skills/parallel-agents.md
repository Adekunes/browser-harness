# Parallel Agents

Run several agents at once, each in its own private Chrome. No shared cookies, tabs, or focus, and no cloud account needed.

## One browser per agent

Give every agent a unique `BU_NAME` and set `BH_LAUNCH_BROWSER=1` on every call. The first call launches a headless Chrome with a temp profile; later calls with the same name reuse it.

```bash
BU_NAME=agent1 BH_LAUNCH_BROWSER=1 browser-harness <<'PY'
new_tab("https://example.com/contact")
click("#name"); type_text("Ada")
print(page_info())
PY
```

Close it when the agent is done. This kills that Chrome and deletes its profile:

```bash
BU_NAME=agent1 browser-harness --reload
```

Forgotten browsers close on their own after `BH_IDLE_TIMEOUT` seconds without a call (default 1800). On Linux they also die with the daemon if it is killed.

## Orchestrating

1. Split the work into one list per agent (3-5 agents is usually plenty; more mostly adds rate-limit risk).
2. Start each sub-agent with its name in the prompt: "Use `BU_NAME=agent2 BH_LAUNCH_BROWSER=1` on every browser-harness call. Close with `BU_NAME=agent2 browser-harness --reload` when done."
3. Have each agent report results as structured text (a markdown table or JSON) rather than sharing files.
4. If an agent hits a CAPTCHA, login wall, or rate limit, it should stop and report, not retry blindly.

Check or close everything from the orchestrator:

```bash
browser-harness list                      # name<TAB>url<TAB>title per live daemon
for n in $(browser-harness list | cut -f1); do BU_NAME=$n browser-harness --reload; done   # close all
```

## Knobs

- `BH_HEADLESS=0` shows each window, useful to watch or to log in by hand once.
- `BH_STEALTH=1` patches headless fingerprint tells for bot-sensitive sites.
- `BH_CHROME_BIN=/path/to/chrome` if auto-detect picks the wrong browser.
- Use a short `BH_RUNTIME_DIR` (e.g. `/tmp/bh`) if the default home path is long; sockets have a ~100 byte path limit.

For logged-in sessions or clean residential IPs, use cloud browsers instead (`start_remote_daemon`).
