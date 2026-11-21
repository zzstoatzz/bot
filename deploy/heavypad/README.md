# phi on heavypad

Phi runs as the `phi.service` systemd user unit on heavypad: one Docker
container from this repository's `Dockerfile`, published on `127.0.0.1:8801`.

- **public URL**: `phi.zzstoatzz.io` is a proxied CNAME to the home Cloudflare
  tunnel, whose ingress list (`~/home-mcp/home/deploy/cloudflared.yml` on
  heavypad) routes the hostname to `http://127.0.0.1:8801`.
- **secrets**: `~/.config/phi/env`, mode 0600, one `NAME=value` per line with
  no quoting. `fly.toml`'s old `[env]` values are set in the unit.
- **state**: `~/.local/state/phi/data`, mounted at `/data`. Files are owned by
  root because the container runs as root.
- **deploy**: `just deploy` from a laptop, or `deploy/heavypad/deploy.sh [ref]`
  on heavypad. It builds the image, tags the old one `phi:previous`, restarts
  the unit, and restores the previous image if `/health` is not `healthy` or
  `degraded` within two minutes.
- **logs**: `DOCKER_HOST=unix:///var/run/docker.sock docker logs -f phi`, or
  `journalctl --user -u phi`.

Only one phi may poll at a time. Stop this unit before starting her anywhere
else, or two instances will answer the same notification.
