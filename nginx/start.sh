#!/bin/sh
# nginx's start-up: use the https config once a certificate exists, otherwise the http-only one, and switch by itself when
# certbot finishes. Also reloads every 6 hours so a renewed certificate is picked up.
set -eu
CONF=/etc/nginx/conf.d/default.conf
SRC=/etc/nginx/templates-src

# 0 when the config changed
render() {
  if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then name=https; else name=http-only; fi
  envsubst '${DOMAIN}' < "$SRC/$name.conf.template" > /tmp/next.conf
  if cmp -s /tmp/next.conf "$CONF"; then return 1; fi
  cp /tmp/next.conf "$CONF"
  echo "nginx: using the $name config"
}

render || true
(while :; do sleep 30; if render; then nginx -t && nginx -s reload; fi; done) &
(while :; do sleep 21600; nginx -s reload; done) &
exec nginx -g 'daemon off;'
