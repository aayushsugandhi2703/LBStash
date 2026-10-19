"""Time limits."""

ACCESS_TTL_SECONDS = 15 * 60
# A session ends this long after sign-in, whatever the activity.
SESSION_MAX_DAYS = 30
# A session untouched for this long is dead.
SESSION_IDLE_HOURS = 12
LOGIN_CHALLENGE_MINUTES = 5
RESET_CHALLENGE_MINUTES = 10
PASSKEY_CHALLENGE_MINUTES = 5
EMAIL_LINK_HOURS = 24
DELETE_GRACE_DAYS = 7
# Wrong second-step attempts per sign-in before the password is needed again.
MAX_CHALLENGE_ATTEMPTS = 5
