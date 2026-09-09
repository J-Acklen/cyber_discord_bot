"""pwn.college account linking: members prove ownership of a pwn.college
account via a one-time code placed in their public "Affiliation" profile
field, then the bot tracks their Linux Luminarium module progress against
pwn.college's public, unauthenticated JSON API and auto-grants a Discord
role on full completion.

No pwn.college credentials are ever requested or stored - only a public
username and what pwn.college already publishes for anyone to see at
https://pwn.college/hacker/<username>.
"""

import logging
import os
import re
import secrets
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger("bot.pwncollege")

BASE_URL = "https://pwn.college"
API_BASE = f"{BASE_URL}/pwncollege_api/v1"
DOJO_ID = "linux-luminarium"
DOJO_NAME = "Linux Luminarium"
COMPLETION_ROLE_ID = os.getenv("PWNCOLLEGE_COMPLETION_ROLE_ID")
USER_AGENT = "UNG-Cyber-Unit-Discord-Bot/1.0 (+https://github.com/J-Acklen/cyber_discord_bot)"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
MODULES_CACHE_TTL = 3600  # dojo structure barely changes; refetch at most hourly

AFFILIATION_RE = re.compile(r'<span class="badge badge-primary">\s*([^<]+?)\s*</span>')


class PwnCollegeError(Exception):
    """Raised for any recoverable pwn.college lookup failure, with a user-facing message."""


class PwnCollege(commands.Cog):
    pwn_group = app_commands.Group(name="pwn", description="Link and track pwn.college progress")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self._modules_cache: list[dict] | None = None
        self._modules_cached_at: float = 0.0

    async def cog_load(self):
        self.session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        self.refresh_completions.start()

    async def cog_unload(self):
        self.refresh_completions.cancel()
        if self.session:
            await self.session.close()

    # --- pwn.college HTTP helpers ---

    async def _get_modules(self) -> list[dict]:
        now = time.monotonic()
        if self._modules_cache is not None and (now - self._modules_cached_at) < MODULES_CACHE_TTL:
            return self._modules_cache

        try:
            async with self.session.get(f"{API_BASE}/dojos/{DOJO_ID}/modules") as resp:
                if resp.status != 200:
                    raise PwnCollegeError("pwn.college's dojo API didn't respond normally - try again later.")
                data = await resp.json()
        except aiohttp.ClientError as e:
            raise PwnCollegeError("Couldn't reach pwn.college right now - try again later.") from e

        modules = data.get("modules", [])
        self._modules_cache = modules
        self._modules_cached_at = now
        return modules

    async def _get_solves(self, username: str) -> list[dict]:
        try:
            async with self.session.get(
                f"{API_BASE}/dojos/{DOJO_ID}/solves", params={"username": username}
            ) as resp:
                if resp.status == 400:
                    raise PwnCollegeError(
                        f"pwn.college doesn't recognize the username `{username}` (or that profile is hidden)."
                    )
                if resp.status != 200:
                    raise PwnCollegeError("Couldn't reach pwn.college right now - try again later.")
                data = await resp.json()
        except aiohttp.ClientError as e:
            raise PwnCollegeError("Couldn't reach pwn.college right now - try again later.") from e

        return data.get("solves", [])

    async def _get_affiliation(self, username: str) -> str | None:
        try:
            async with self.session.get(f"{BASE_URL}/hacker/{username}") as resp:
                if resp.status == 404:
                    raise PwnCollegeError(
                        f"No public pwn.college profile found for `{username}`. Check the spelling, and make "
                        "sure your profile isn't set to hidden in pwn.college settings."
                    )
                if resp.status != 200:
                    raise PwnCollegeError("Couldn't reach pwn.college right now - try again later.")
                html = await resp.text()
        except aiohttp.ClientError as e:
            raise PwnCollegeError("Couldn't reach pwn.college right now - try again later.") from e

        match = AFFILIATION_RE.search(html)
        return match.group(1).strip() if match else None

    async def _compute_progress(self, username: str) -> tuple[list[dict], int, int]:
        """Returns (per_module_progress, overall_solved, overall_total)."""
        modules = await self._get_modules()
        solves = await self._get_solves(username)

        solved_by_module: dict[str, set[str]] = {}
        for solve in solves:
            solved_by_module.setdefault(solve["module_id"], set()).add(solve["challenge_id"])

        progress = []
        overall_solved = 0
        overall_total = 0
        for module in modules:
            required_ids = {c["id"] for c in module["challenges"] if c.get("required", True)}
            if not required_ids:
                continue
            solved_ids = solved_by_module.get(module["id"], set()) & required_ids
            progress.append({
                "id": module["id"],
                "name": module["name"],
                "solved": len(solved_ids),
                "total": len(required_ids),
            })
            overall_solved += len(solved_ids)
            overall_total += len(required_ids)

        return progress, overall_solved, overall_total

    async def _maybe_grant_role(self, guild: discord.Guild, member: discord.Member) -> bool:
        """Grants the completion role if configured and not already recorded. Returns True if newly granted."""
        if not COMPLETION_ROLE_ID:
            return False
        role = guild.get_role(int(COMPLETION_ROLE_ID))
        if not role or role in member.roles:
            return False
        await member.add_roles(role, reason=f"Completed {DOJO_NAME} on pwn.college")
        return True

    # --- commands ---

    @pwn_group.command(name="link", description="Start linking your pwn.college account.")
    @app_commands.describe(username="Your pwn.college username")
    async def pwn_link(self, interaction: discord.Interaction, username: str):
        code = f"cyberunit-{secrets.token_hex(3)}"
        db = self.bot.db
        await db.execute(
            "INSERT INTO pwncollege_links (guild_id, user_id, username, verify_code) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (guild_id, user_id) DO UPDATE SET username = excluded.username, "
            "verify_code = excluded.verify_code, verified = 0, role_granted = 0, linked_at = NULL",
            (interaction.guild.id, interaction.user.id, username, code),
        )
        await db.commit()

        await interaction.response.send_message(
            "**Step 1:** Go to your pwn.college profile settings (https://pwn.college/settings#profile)\n"
            f"**Step 2:** Set your **Affiliation** field to exactly: `{code}`\n"
            "**Step 3:** Save, then run `/pwn verify` here.\n"
            "You can change your affiliation back to anything you like once verified.",
            ephemeral=True,
        )

    @pwn_group.command(name="verify", description="Finish linking your pwn.college account.")
    async def pwn_verify(self, interaction: discord.Interaction):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT username, verify_code, verified FROM pwncollege_links WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("Run `/pwn link` first.", ephemeral=True)
            return
        if row["verified"]:
            await interaction.response.send_message(f"You're already linked as `{row['username']}`.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            affiliation = await self._get_affiliation(row["username"])
        except PwnCollegeError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        if affiliation != row["verify_code"]:
            await interaction.followup.send(
                f"Didn't find the code yet - double check your Affiliation field is set to exactly "
                f"`{row['verify_code']}` and saved, then try again.",
                ephemeral=True,
            )
            return

        await db.execute(
            "UPDATE pwncollege_links SET verified = 1, linked_at = datetime('now') "
            "WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )
        await db.commit()

        message = f"Linked! Your Discord is now connected to pwn.college user `{row['username']}`."
        try:
            _, solved, total = await self._compute_progress(row["username"])
            message += f"\nCurrent {DOJO_NAME} progress: **{solved}/{total}** challenges."
            if total and solved == total:
                granted = await self._maybe_grant_role(interaction.guild, interaction.user)
                if granted:
                    message += "\nYou've completed the dojo - role granted! \U0001F389"
                    await db.execute(
                        "UPDATE pwncollege_links SET role_granted = 1 WHERE guild_id = ? AND user_id = ?",
                        (interaction.guild.id, interaction.user.id),
                    )
                    await db.commit()
        except PwnCollegeError:
            pass  # linking itself still succeeded; progress can be checked later with /pwn progress

        await interaction.followup.send(message, ephemeral=True)

    @pwn_group.command(name="progress", description=f"Show {DOJO_NAME} progress for yourself or another member.")
    @app_commands.describe(member="Whose progress to show (defaults to you)")
    async def pwn_progress(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        db = self.bot.db
        cursor = await db.execute(
            "SELECT username, role_granted FROM pwncollege_links WHERE guild_id = ? AND user_id = ? AND verified = 1",
            (interaction.guild.id, member.id),
        )
        row = await cursor.fetchone()
        if not row:
            pronoun = "You haven't" if member == interaction.user else f"{member.mention} hasn't"
            await interaction.response.send_message(f"{pronoun} linked a pwn.college account yet.", ephemeral=(member == interaction.user))
            return

        await interaction.response.defer()

        try:
            progress, solved, total = await self._compute_progress(row["username"])
        except PwnCollegeError as e:
            await interaction.followup.send(str(e))
            return

        lines = []
        for m in progress:
            check = "✅" if m["solved"] == m["total"] else "▫️"
            lines.append(f"{check} {m['name']}: {m['solved']}/{m['total']}")

        embed = discord.Embed(
            title=f"{DOJO_NAME} Progress: {row['username']}",
            description="\n".join(lines),
            color=discord.Color.green() if solved == total else discord.Color.blurple(),
        )
        embed.set_footer(text=f"Overall: {solved}/{total} required challenges")
        await interaction.followup.send(embed=embed)

        if total and solved == total and not row["role_granted"]:
            granted = await self._maybe_grant_role(interaction.guild, member)
            if granted:
                await db.execute(
                    "UPDATE pwncollege_links SET role_granted = 1 WHERE guild_id = ? AND user_id = ?",
                    (interaction.guild.id, member.id),
                )
                await db.commit()
                await interaction.followup.send(f"\U0001F389 {member.mention} completed {DOJO_NAME} - role granted!")

    @pwn_group.command(name="unlink", description="Remove your pwn.college link.")
    async def pwn_unlink(self, interaction: discord.Interaction):
        db = self.bot.db
        await db.execute(
            "DELETE FROM pwncollege_links WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, interaction.user.id),
        )
        await db.commit()
        await interaction.response.send_message("Unlinked your pwn.college account.", ephemeral=True)

    # --- background auto-role check ---

    @tasks.loop(hours=6)
    async def refresh_completions(self):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT guild_id, user_id, username FROM pwncollege_links WHERE verified = 1 AND role_granted = 0"
        )
        rows = await cursor.fetchall()
        for row in rows:
            guild = self.bot.get_guild(row["guild_id"])
            if not guild:
                continue
            member = guild.get_member(row["user_id"])
            if not member:
                continue
            try:
                _, solved, total = await self._compute_progress(row["username"])
            except PwnCollegeError as e:
                log.warning("pwn.college progress check failed for %s: %s", row["username"], e)
                continue
            if total and solved == total:
                try:
                    granted = await self._maybe_grant_role(guild, member)
                except discord.HTTPException as e:
                    log.warning("Failed to grant pwn.college completion role to %s: %s", member, e)
                    continue
                if granted:
                    await db.execute(
                        "UPDATE pwncollege_links SET role_granted = 1 WHERE guild_id = ? AND user_id = ?",
                        (row["guild_id"], row["user_id"]),
                    )
                    await db.commit()
                    log.info("Granted pwn.college completion role to %s", member)

    @refresh_completions.before_loop
    async def before_refresh_completions(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PwnCollege(bot))
