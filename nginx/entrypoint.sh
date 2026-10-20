#!/bin/sh
# Starts nginx. Uses the https config if a certificate exists, otherwise http, and switches by itself when it appears.
# Also reloads every 6 hours to pick up renewed certificates.
set -eu
CONF=/etc/nginx/conf.d/default.conf
SRC=/etc/nginx/templates-src
CHECK_EVERY=30        # seconds between certificate checks
RELOAD_EVERY=21600    # seconds between reloads (6 hours)

# Writes the right template to $CONF. Returns 0 if the config changed.
render() {
  if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then name=https; else name=http; fi
  envsubst '${DOMAIN}' < "$SRC/$name.conf.template" > /tmp/next.conf
  if cmp -s /tmp/next.conf "$CONF"; then return 1; fi
  cp /tmp/next.conf "$CONF"
  echo "nginx: using the $name config"
}

render || true
(
  waited=0
  while :; do
    sleep "$CHECK_EVERY"
    waited=$((waited + CHECK_EVERY))
    if render; then
      nginx -t && nginx -s reload
      waited=0
    elif [ "$waited" -ge "$RELOAD_EVERY" ]; then
      nginx -s reload
      waited=0
    fi
  done
) &
exec nginx -g 'daemon off;'
