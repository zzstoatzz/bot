# runtime health

`/health` returns 503 when the poller is stopped without being paused or when
no poll iteration has completed in `health_stale_after` seconds (default 30x
`notification_poll_interval`). fly's http check (30s) only stops routing to a
failing machine; fly restarts a machine when its process exits (`[[restart]]`
policy `always`, so an upstream outage cannot exhaust a finite restart budget). so `core/watchdog.py` applies the same decision every 15s
and exits the process non-zero. the check's `grace_period` covers startup (auth,
schedule seeding — 60s is Fly's cap; bio refresh runs in the background) so a booting machine
is not marked failing.
