#!/bin/sh
# Gets the Let's Encrypt certificate when it is missing, then renews it. Does nothing until LETSENCRYPT_EMAIL is set in .env.
if [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "certbot: LETSENCRYPT_EMAIL is not set in .env, so no certificate is requested and the app stays on http."
  while :; do sleep 86400; done
fi
STAGING=""
[ "${LETSENCRYPT_STAGING:-0}" = 1 ] && STAGING="--staging"

while :; do
  if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    certbot renew --webroot -w /var/www/certbot --quiet || echo "certbot: renew failed, trying again later"
    sleep 43200
  else
    echo "certbot: requesting a certificate for $DOMAIN"
    if ! certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --cert-name "$DOMAIN" \
      --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive $STAGING; then
      echo "certbot: failed. Check that the DNS A record for $DOMAIN points here and that ports 80 and 443 are open. Trying again in 30 minutes."
      sleep 1800
    fi
  fi
done
