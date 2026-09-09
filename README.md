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

**Role linking** (staff only): `/rolelink add`, `/rolelink remove`,
`/rolelink list` - configure "if a member gets role X, auto-give them role Y".
Example: `/rolelink add trigger_role:S-1 linked_role:Staff Officer`.

**CTF tracker**: `/ctf add` `/ctf remove` (staff only), `/ctf list`
`/ctf submit` `/ctf scoreboard` (everyone).

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
data/bot.sqlite3     created automatically on first run
```
