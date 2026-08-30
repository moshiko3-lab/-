#!/usr/bin/env bash
#
# Everything in the WhatsApp setup that a script can do, in one run.
#
#   bash supabase/setup_whatsapp.sh          set it all up
#   bash supabase/setup_whatsapp.sh --check  say what is set up and what is not
#
# What it does: links the project, runs the two SQL files, invents the two
# secrets nobody should be inventing by hand, sets all five on the function,
# deploys it, then proves the webhook answers -- and prints the three things
# that have to be pasted into Meta's own panels afterwards.
#
# What it cannot do: the Meta side. Opening the number, the permanent token,
# the webhook form and the two message templates are all clicks in Meta's
# console, and no key exists that would let a script do them.
#
# Nothing here writes a secret to a file that survives the run, and nothing
# here goes into the repository. The values live on the function, which is the
# only thing that ever needs them.

set -euo pipefail

PROJECT_REF="bxjwqvoscbzhetuwhyvk"
FUNC="https://${PROJECT_REF}.supabase.co/functions/v1/whatsapp"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVFILE=""

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
ok()    { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()   { printf '  \033[31m✗\033[0m %s\n' "$*"; }
ask()   { local p="$1" v; read -r -p "  $p " v; printf '%s' "$v"; }
asks()  { local p="$1" v; read -r -s -p "  $p " v; printf '\n' >&2; printf '%s' "$v"; }

need() {
  command -v "$1" >/dev/null 2>&1 && return 0
  bad "$1 is not installed. $2"
  return 1
}

# ---------------------------------------------------------------- --check
check() {
  bold "Where the WhatsApp setup has got to"

  step "The tools"
  command -v supabase >/dev/null 2>&1 \
    && ok "supabase CLI $(supabase --version 2>/dev/null | head -1)" \
    || bad "supabase CLI missing — https://supabase.com/docs/guides/cli"

  step "The secrets on the function"
  if command -v supabase >/dev/null 2>&1; then
    local list
    list="$(supabase secrets list 2>/dev/null || true)"
    if [ -z "$list" ]; then
      warn "could not read them — is the project linked? (supabase link --project-ref $PROJECT_REF)"
    else
      for k in WA_TOKEN WA_PHONE_ID WA_VERIFY_TOKEN WA_APP_SECRET WA_TICK_SECRET; do
        if printf '%s' "$list" | grep -q "$k"; then ok "$k is set"; else bad "$k is missing"; fi
      done
    fi
  fi

  step "The function itself"
  # curl prints 000 itself when it never connected, so take its word for it
  # rather than adding a second 000 behind a || and matching neither case
  local code="000" out
  if out="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
            "${FUNC}/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=x" 2>/dev/null)"
  then code="$out"; fi
  case "$code" in
    403) ok "deployed and answering (it refused a wrong verify token, which is right)";;
    404) bad "deployed but /webhook is not there — deploy again";;
    000) bad "no answer at all — not deployed, or no network to Supabase";;
    *)   warn "answered $code, which is not one of the expected ones";;
  esac

  step "The clock"
  echo "  Run this in the SQL editor to see whether the tick is firing:"
  echo "    select * from cron.job_run_details order by start_time desc limit 10;"
  echo
  bold "The Meta side cannot be checked from here."
  echo "  The manager's WhatsApp → Setup tab reads it live: open it and look."
}

# ------------------------------------------------------------------- run
main() {
  bold "Connecting the school's WhatsApp"
  echo "Project ${PROJECT_REF}. Ctrl-C at any point leaves everything as it was."

  need supabase "https://supabase.com/docs/guides/cli — then: supabase login" || exit 1
  need curl "install curl" || exit 1
  need openssl "install openssl, or pass the two secrets in by hand" || exit 1

  # ---- the project
  step "Linking the project"
  if supabase link --project-ref "$PROJECT_REF" >/dev/null 2>&1; then
    ok "linked"
  else
    warn "link failed — run 'supabase login' first, then this script again"
    exit 1
  fi

  # ---- the tables
  step "The tables"
  local dburl="${SUPABASE_DB_URL:-}"
  if [ -z "$dburl" ]; then
    echo "  A direct database URL runs the two SQL files from here."
    echo "  Supabase → Project settings → Database → Connection string → URI."
    echo "  Leave it empty to paste the files into the SQL editor by hand instead."
    dburl="$(asks 'Database URL (hidden, optional):')"
  fi
  if [ -n "$dburl" ] && command -v psql >/dev/null 2>&1; then
    psql "$dburl" -v ON_ERROR_STOP=1 -q -f "$HERE/schema.sql"   && ok "schema.sql ran"
    psql "$dburl" -v ON_ERROR_STOP=1 -q -f "$HERE/whatsapp.sql" && ok "whatsapp.sql ran"
  else
    [ -n "$dburl" ] && warn "psql is not installed, so the files were not run from here"
    warn "paste these two into the SQL editor, in this order, then come back:"
    echo "      $HERE/schema.sql"
    echo "      $HERE/whatsapp.sql"
    read -r -p "  Press return once both have run. " _
  fi

  # ---- what only Meta can give
  step "The four values from Meta"
  echo "  WhatsApp → API setup gives the first two; Business settings →"
  echo "  System users gives the token; App settings → Basic gives the secret."
  local phone_id token app_secret
  phone_id="$(ask   'Phone number ID:')"
  token="$(asks     'Permanent access token (hidden):')"
  app_secret="$(asks 'App secret (hidden):')"
  [ -n "$phone_id" ] && [ -n "$token" ] || { bad "both are needed"; exit 1; }
  [ -n "$app_secret" ] || warn "no app secret: the webhook will not be able to check Meta's signature"

  # ---- the two nobody should invent by hand
  local verify_token tick_secret
  verify_token="$(openssl rand -hex 24)"
  tick_secret="$(openssl rand -hex 24)"
  ok "invented a webhook verify token and a tick secret"

  # ---- onto the function
  #
  # Through a file rather than on the command line: arguments are visible in
  # `ps` to anyone else on the machine, and a token that can message the world
  # as the school should not be sitting there for the length of a deploy.
  step "Setting them on the function"
  umask 077
  ENVFILE="$(mktemp)"
  # the trap outlives this function, so the name it cleans up has to as well
  trap 'rm -f "${ENVFILE:-}"' EXIT INT TERM
  {
    printf 'WA_TOKEN=%s\n'        "$token"
    printf 'WA_PHONE_ID=%s\n'     "$phone_id"
    printf 'WA_VERIFY_TOKEN=%s\n' "$verify_token"
    printf 'WA_APP_SECRET=%s\n'   "$app_secret"
    printf 'WA_TICK_SECRET=%s\n'  "$tick_secret"
  } > "$ENVFILE"
  supabase secrets set --env-file "$ENVFILE" >/dev/null
  rm -f "$ENVFILE"
  ok "five secrets set"

  # ---- deploy
  step "Deploying the function"
  supabase functions deploy whatsapp --no-verify-jwt
  ok "deployed"

  # ---- prove it
  step "Proving the webhook answers"
  local got
  got=""
  got="$(curl -s --max-time 25 \
        "${FUNC}/webhook?hub.mode=subscribe&hub.verify_token=${verify_token}&hub.challenge=shokogi" \
        2>/dev/null || true)"
  if [ "$got" = "shokogi" ]; then
    ok "it answered its own challenge — Meta's verification will pass"
  else
    bad "it answered '${got}' instead of 'shokogi'. Deploy again, then re-run with --check."
  fi

  # ---- what is left, with the values already in it
  cat <<EOF

$(bold "Three things are left, and all three are in Meta or the SQL editor.")

1. Meta app → WhatsApp → Configuration → Webhook → Edit:

     Callback URL   ${FUNC}/webhook
     Verify token   ${verify_token}

   Verify and save, then Manage → subscribe to the field "messages".
   Nothing arrives without that, and the panel does not say so.

2. WhatsApp Manager → Message templates. Two, both Utility, language en:

     session_reminder
       Hi {{1}}, a reminder from Shokogi Surf School: {{2}} is on {{3}}.
       Reply here if anything has changed. See you on the water.

     daily_brief
       Shokogi, {{1}}. Today: {{2}}

3. SQL editor — switch on pg_cron and pg_net under Database → Extensions,
   then run this so reminders and the brief actually go out:

     select cron.schedule('whatsapp-tick', '*/5 * * * *', \$cron\$
       select net.http_post(
         url     := '${FUNC}/tick',
         headers := jsonb_build_object('Content-Type','application/json',
                                       'x-wa-secret','${tick_secret}'),
         body    := '{}'::jsonb) \$cron\$);

$(bold "The verify token and the tick secret are printed once, here.")
They are on the function already; this is the only copy you will see. If this
window is lost, run the script again — it invents new ones and resets both.

Then open the manager → WhatsApp → Setup. Every line should say "set".
EOF
}

case "${1:-}" in
  --check|-c) check;;
  --help|-h)  awk 'NR>1 && /^#/ {sub(/^# ?/,""); print; next} NR>1 {exit}' \
                "${BASH_SOURCE[0]}";;
  "")         main;;
  *)          bad "unknown option: $1"; exit 2;;
esac
