# runtime health

`/health` returns 503 when the poller is stopped without being paused or when
no poll iteration has completed in `health_stale_after` seconds (default 30x
`notification_poll_interval`). nothing outside the process acts on that status:
systemd restarts `phi.service` only when the container exits (`Restart=always`,
so an upstream outage cannot exhaust a finite restart budget). so
`core/watchdog.py` applies the same decision every 15s and exits the process
non-zero. startup (auth, schedule seeding; bio refresh runs in the background)
finishes well inside the two minutes `deploy/heavypad/deploy.sh` waits before
it restores the previous image.

`/health` reports `degraded` (still 200) when a model's provider refuses its
account: out of credits or quota, or a key it rejects. Every model phi builds
goes through `core/model_health.py`, which marks the model unavailable on
such a refusal and clears it on that model's next answered request. The poll
loop keeps ticking through an outage like that, so liveness alone reads
healthy while every run fails; a restart cannot fix it and a 503 would take
the site off routing, so the watchdog ignores it. `reason` and
`models_unavailable` name the model, the site's status pill reads
"model unavailable", and the Prefect `phi-trigger` validation, which requires
`healthy`, refuses to start a pass. The state is per process: a restart
reads healthy until the next refused request.

## private recovery watch

Set `RECOVERY_MCP_URL` to the alerts service's `/phi/mcp` and
`RECOVERY_MCP_TOKEN` to Phi's dedicated bearer to enable the background
watch. Poll failures retain the cursor in the operator report database.
Phi respects pause and operator override, probes Pollz again, and records
the private DM through the existing receipt ledger.
