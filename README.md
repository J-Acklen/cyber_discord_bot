# UNG Cyber Unit Discord Bot

Slash-command bot for the UNG Cyber Unit Discord server: moderation, utility
commands, a lightweight CTF tracker, and automatic linked-role assignment
(e.g. giving someone the `S-1` role auto-grants `Staff Officer`).

## 1. Create the bot in Discord's Developer Portal

1. Go to https://discord.com/developers/applications -> New Application.
2. Under **Bot**, click "Reset Token" to get your bot token (keep it secret).
3. On the same page, enable the **Server Members Intent** (required for
   moderation lookups and linked roles).
4. Under **OAuth2 -> URL Generator**, check scopes `bot` and
   `applications.commands`, and under Bot Permissions check at least:
   Kick Members, Ban Members, Moderate Members, Manage Roles, Manage
   Messages, Read Messages/View Channels, Send Messages, Embed Links.
5. Open the generated URL and invite the bot to the UNG Cyber Unit server.
6. In Discord, make sure the bot's role is positioned **above** any role it
   needs to manage (e.g. above `Staff Officer` for role-linking, above roles
   it needs to remove via moderation).

## 2. Configure

```bash
cp .env.example .env
```

Fill in:
- `DISCORD_TOKEN` - the bot token from step 1.
- `GUILD_ID` (optional) - your server's ID; if set, slash commands sync
  instantly to that server instead of taking up to an hour globally. Right-click
  the server icon with Developer Mode enabled to copy the ID.
- `ADMIN_ROLE_ID` (optional) - a role ID that can run staff-only commands
  even without the Manage Server permission (e.g. your officer role).

## 3. Run it

### Option A: Docker (recommended for permanent hosting)

```bash
docker compose up -d --build
```

Logs: `docker compose logs -f`. The bot restarts automatically on crash or
server reboot (`restart: unless-stopped`). SQLite data persists in `./data`.

**Redeploying after code changes:**

```bash
./deploy.sh
```

Pulls the latest commit, rebuilds the image, and restarts the container.

**Backing up the database:** `data/bot.sqlite3` holds warnings, role links,
and the CTF challenges/scoreboard. Back it up with:

```bash
./backup.sh
```

This makes a consistent snapshot (safe to run while the bot is up) into
`~/backups`, keeping the 14 most recent copies. Requires the `sqlite3` CLI on
the host (`sudo apt install sqlite3`). To run it automatically every night at
3 AM, add this to `crontab -e`:

```
0 3 * * * /home/ubuntu/cyber_discord_bot/backup.sh >> /home/ubuntu/backups/backup.log 2>&1
```

### Option B: Directly on a Linux VPS with systemd

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo cp cyber-discord-bot.service.example /etc/systemd/system/cyber-discord-bot.service
# edit the User= and WorkingDirectory= paths in that file
sudo systemctl daemon-reload
sudo systemctl enable --now cyber-discord-bot
```

Check status: `systemctl status cyber-discord-bot`. Logs: `journalctl -u cyber-discord-bot -f`.

### Local testing

```bash
pip install -r requirements.txt
python bot.py
```

## Commands

**Moderation** (staff only): `/kick` `/ban` `/unban` `/timeout` `/untimeout`
`/warn` `/warnings` `/clearwarnings` `/purge`

**Utility** (everyone): `/ping` `/userinfo` `/serverinfo` `/roleinfo` `/avatar`
`/commands` - lists every command, grouped by category, in a reply only you
can see (🔒 marks staff-only ones).

**Role linking** (staff only): `/rolelink add`, `/rolelink remove`,
`/rolelink list` - configure "if a member gets role X, auto-give them role Y
- and if role X is taken away, auto-remove role Y too." Both directions are
mirrored automatically from one link.
Example: `/rolelink add trigger_role:S-1 linked_role:Staff Officer`.

**CTF tracker**: `/ctf add` `/ctf remove` (staff, or anyone holding the role
configured as `CTF_ADMIN_ROLE_ID`), `/ctf list` `/ctf submit` `/ctf
scoreboard` (everyone). `/ctf submit` is rate-limited to one attempt per 5
seconds per user to slow down flag brute-forcing.

**Roll call / accountability** (staff only to start/report/close):
`/rollcall start title:<text> [required_role]` posts an embed members react
to with ✅ (present) or 🟡 (excused). `/rollcall report id:<n>` lists who
checked in, and - if `required_role` was set - who from that role hasn't
responded at all. `/rollcall close id:<n>` stops new reactions from
counting. `/rollcall list` shows recent roll call IDs.

**Resource library** (staff only to add/remove; everyone can search/list):
`/resource add title: url: category:` adds a link to a shared, searchable
catalog of tools, writeups, and practice rooms. `/resource search query:`
and `/resource list [category]` browse it; `/resource remove id:` cleans it up.

**pwn.college progress tracking** (everyone): `/pwn link username:` starts
linking a pwn.college account - the bot gives a one-time code (a placeholder
URL) to place in your pwn.college **Website** field (Account Settings),
proving you own that account without ever handling a password or API token.
Website is used instead of Affiliation because it only appears in a hover
tooltip/link on your profile, not as visible page text - Affiliation works
too if you'd rather use that, but it *is* shown as plain text to anyone
viewing your profile. `/pwn verify` confirms it. `/pwn progress [member]`
shows Linux Luminarium module-by-module
completion for yourself or another linked member, and auto-grants the role
configured as `PWNCOLLEGE_COMPLETION_ROLE_ID` the moment all required
challenges are solved (also checked automatically every 6 hours in the
background, so completing the dojo doesn't require re-running the command).
`/pwn unlink` removes your link. All progress data comes from pwn.college's
own public, unauthenticated API - no credentials are ever requested.

"Staff only" means the user has Discord's Manage Server permission, or holds
the role configured as `ADMIN_ROLE_ID`.

## Project layout

```
bot.py              entrypoint: intents, cog loading, command sync, error handler
database.py         SQLite schema + connection setup (shared via bot.db)
cogs/checks.py       shared staff-permission check
cogs/moderation.py   kick/ban/timeout/warn/purge
cogs/utility.py      ping/userinfo/serverinfo/roleinfo/avatar
cogs/autorole.py     linked-role config + on_member_update listener
cogs/ctf.py          challenge CRUD, flag submission, scoreboard
cogs/rollcall.py     reaction-based check-ins + missing-member reports
cogs/resources.py    shared, searchable link/tool/writeup catalog
cogs/pwncollege.py   pwn.college account linking + Linux Luminarium progress
data/bot.sqlite3     created automatically on first run
```

## Security posture

Last audited 2026-09-09. Summary of what's in place, for future reference:

- **No inbound network surface beyond SSH.** `docker-compose.yml` never
  publishes container ports; a port scan of the public IP confirms only 22
  responds.
- **SQL injection**: every query is parameterized (`?` placeholders) - no
  string-built SQL anywhere.
- **Errors never leak to Discord**: the global handler logs full tracebacks
  server-side, sends only a generic message to the user.
- **Dependencies**: scanned with `pip-audit`, no known CVEs at time of audit
  - worth re-running occasionally (`pip install pip-audit && pip-audit -r
  requirements.txt`).
- **Container runs as a non-root user** (not root), limiting blast radius if
  a dependency or future code change were ever compromised.
- **VM hardening**: fail2ban active on SSH, `PermitRootLogin no`,
  `X11Forwarding no`, unattended security upgrades enabled, unused
  `rpcbind` service disabled.
- **`/ctf submit` is rate-limited** (1 per 5s per user) to slow down flag
  brute-forcing. Flags are stored in plaintext in the DB by design choice -
  the DB never leaves the VM and isn't exposed on any port.
