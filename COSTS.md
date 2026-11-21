# COSTS.md

> **Mandate.** This file tracks the infrastructure costs attributed to **bot** and
> what we're doing to bring them down. It is the running record of what this project
> spends, why, and a changelog of changes that moved the number. If the spend here is
> unjustified, that's a signal to clean up — not to ignore it.

## current cost — fetch it live, never hardcode

Costs drift, so this file deliberately does **not** hardcode a dollar figure. Get the
current monthly cost for this repo from the daily snapshot (collected by
`my-prefect-server`, surfaced at https://hub.waow.tech):

```bash
curl -s https://hub.waow.tech/api/costs.json | jq '{
  as_of: .generatedAt,
  this_repo_monthly_usd: (
    [ .lineItems[] | select((.service | split(":" )[0]) as $s | ["zzstoatzz-phi"] | index($s)) ]
    | if length == 0 then null else (map(.amount) | add) / 100 end
  ),
  lines: [ .lineItems[] | select((.service | split(":" )[0]) as $s | ["zzstoatzz-phi"] | index($s))
           | {service, provider, usd: (.amount/100), estimated} ]
}'
```

`null` means no matching provider lines were found; it does not mean free.

Or open the costs panel at https://hub.waow.tech and group **by project**.

Services attributed to this repo: `zzstoatzz-phi`. If that list is
wrong, fix the mapping in `my-prefect-server`
(`packages/mps/src/mps/costs/projects.py`) rather than editing numbers here.

## how we might bring this down
- phi no longer has a hosting line: she runs on heavypad. What remains is usage
  billed by her model and memory providers, which this snapshot does not attribute.

## changelog
- **2026-06-17** — initial cost notice; 1 service(s) attributed here. Run the command above for the live figure.
- **2026-11-20** — moved from the Fly app `zzstoatzz-phi` (shared-cpu-1x, 1 GB, 1 GB volume, about $7.60/month) to a container on heavypad behind the home Cloudflare tunnel.
