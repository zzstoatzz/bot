# Lexidraw subprocess accumulation

Phi's Fly machine remained started while both its HTTP health check and SSH
stopped responding. Restarting machine `6e82043dad4768` restored service at
2026-11-07 04:21 UTC (November 6, 10:21 p.m. CST). The deployed image was
`deployment-01M6QSHY9S67PNVFF3B367TXF6`, release 705.

## Cause

`build_toolsets()` creates a fresh `StdioTransport` for Lexidraw for every
agent run and context-budget composition. FastMCP 4.2.0a1 defaults this
transport to `keep_alive=True`: exiting the connection context releases the
client session but intentionally leaves the transport's subprocess alive.
The transport must instead be scoped to the disposable toolset's lifetime.

Commit `af10fdc` on November 1 replaced PydanticAI's `MCPServerStdio` with
`MCPToolset(StdioTransport(...))` during the FastMCP 4 migration. That introduced
the keep-alive default into this per-run construction path without assigning
an owner to explicitly close the retained subprocess.

The context-budget loop performs this composition every 30 minutes without
requiring an agent run or someone to open the cockpit. After the recovery,
four idle `node /opt/lexidraw/dist/index.js` processes were children of the
Python server. Two were from explicit diagnostic refreshes; the others
preceded those refreshes. Each retained roughly 19 MiB of anonymous memory
and about 62 MiB RSS, which includes shared file-backed pages and must not
be summed as private usage. Python RSS stayed near 375 MiB during the
explicit refreshes even as new Node children appeared.

## Historical machine evidence

Fly Prometheus series were queried for the app and machine on host `7ec2`.
All times here are UTC on November 6–7:

- After an earlier restart at 19:06, available memory was 277 MiB at 19:30.
- Available memory repeatedly fell at the context refreshes: 21:39 (-25 MiB),
  22:09 (-22 MiB), 22:40 (-16 MiB), 01:42 (-16 MiB), 02:13 (-15 MiB),
  and 02:43 (-14 MiB). Agent runs added other steps; these samples do not
  attribute every byte of growth to Lexidraw.
- By 03:00 available memory was zero. The machine had no swap.
- Between 03:10 and 04:20, five-minute CPU accounting showed 81–94% I/O wait,
  negligible user CPU, and effectively no idle CPU. Memory full-pressure
  averages were roughly 45–62% over one-minute windows.
- CPU throttling remained zero; allocated file descriptors were 640 against
  a limit of 95,940. The machine did not record an OOM kill or spontaneous
  process exit before the manual restart.
- Logfire recorded concurrent failures across MCP, Bluesky chat, Jetstream,
  operator PDS reads, and notification polling. The last exported event
  started at 03:12:10. These are consequences of the machine-wide pressure,
  not evidence that every upstream independently failed.
- After restarting the same image and machine, available memory recovered
  to about 371 MiB and memory pressure returned to zero. Health, notification
  polling, Jetstream and Evergreen API/docs probes recovered.

The health check only removes a machine from routing. Fly restarts this app
on process exit. The watchdog is an asyncio task in the same Python process,
and notification fetching invokes the synchronous AT Protocol SDK on the
event-loop thread. It cannot provide independent recovery when that process
is blocked under severe memory pressure. No pre-restart stack capture exists,
so the exact instruction at which the watchdog stopped progressing is unknown.

## Regression and fix

`tests/test_mcp_process_lifecycle.py` builds the production Lexidraw toolset,
substitutes a real local Python MCP server for the Node executable, and checks
the child's PID after leaving the context. Both successful and exceptional
exits left a live process before the fix. With `keep_alive=False`, three fresh
toolsets in each case release their subprocesses before the context returns.

This fixes subprocess ownership without changing tool exposure or publication
guards. It does not add an independent process supervisor or memory profiling.
