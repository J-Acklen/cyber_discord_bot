"""Lightweight in-house CTF tracker: officers add challenges with a hidden
flag, members submit flags via /ctf submit, and /ctf scoreboard tallies points.
"""

import discord
from discord import app_commands
from discord.ext import commands

from .checks import is_staff


class CTF(commands.Cog):
    ctf_group = app_commands.Group(name="ctf", description="CTF challenges and scoreboard")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @ctf_group.command(name="add", description="Add a new CTF challenge.")
    @app_commands.describe(name="Challenge name", category="Category (e.g. web, crypto, pwn)", points="Points awarded", flag="The exact flag string")
    @is_staff()
    async def ctf_add(self, interaction: discord.Interaction, name: str, category: str, points: int, flag: str):
        db = self.bot.db
        try:
            await db.execute(
                "INSERT INTO ctf_challenges (guild_id, name, category, points, flag, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (interaction.guild.id, name, category, points, flag, interaction.user.id),
            )
            await db.commit()
        except Exception:
            await interaction.response.send_message(f"A challenge named `{name}` already exists.", ephemeral=True)
            return
        await interaction.response.send_message(f"Added challenge **{name}** ({category}, {points} pts).", ephemeral=True)

    @ctf_group.command(name="remove", description="Remove a CTF challenge.")
    @app_commands.describe(name="Challenge name to remove")
    @is_staff()
    async def ctf_remove(self, interaction: discord.Interaction, name: str):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT id FROM ctf_challenges WHERE guild_id = ? AND name = ?",
            (interaction.guild.id, name),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message(f"No challenge named `{name}`.", ephemeral=True)
            return

        await db.execute("DELETE FROM ctf_solves WHERE challenge_id = ?", (row["id"],))
        await db.execute("DELETE FROM ctf_challenges WHERE id = ?", (row["id"],))
        await db.commit()
        await interaction.response.send_message(f"Removed challenge **{name}**.")

    @ctf_group.command(name="list", description="List open CTF challenges.")
    async def ctf_list(self, interaction: discord.Interaction):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT name, category, points FROM ctf_challenges WHERE guild_id = ? ORDER BY category, points",
            (interaction.guild.id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No challenges have been added yet.")
            return

        lines = [f"**{row['name']}** ({row['category']}) - {row['points']} pts" for row in rows]
        embed = discord.Embed(title="Open Challenges", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)

    @ctf_group.command(name="submit", description="Submit a flag for a challenge.")
    @app_commands.describe(name="Challenge name", flag="Your flag guess")
    @app_commands.checks.cooldown(1, 5.0)  # 1 attempt per 5s per user, to slow down flag brute-forcing
    async def ctf_submit(self, interaction: discord.Interaction, name: str, flag: str):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT id, flag, points FROM ctf_challenges WHERE guild_id = ? AND name = ?",
            (interaction.guild.id, name),
        )
        challenge = await cursor.fetchone()
        if not challenge:
            await interaction.response.send_message(f"No challenge named `{name}`.", ephemeral=True)
            return

        solve_cursor = await db.execute(
            "SELECT 1 FROM ctf_solves WHERE challenge_id = ? AND user_id = ?",
            (challenge["id"], interaction.user.id),
        )
        if await solve_cursor.fetchone():
            await interaction.response.send_message("You've already solved this challenge.", ephemeral=True)
            return

        if flag.strip() != challenge["flag"]:
            await interaction.response.send_message("Incorrect flag.", ephemeral=True)
            return

        await db.execute(
            "INSERT INTO ctf_solves (challenge_id, guild_id, user_id) VALUES (?, ?, ?)",
            (challenge["id"], interaction.guild.id, interaction.user.id),
        )
        await db.commit()
        await interaction.response.send_message(
            f"Correct! You earned {challenge['points']} points for **{name}**.", ephemeral=True
        )

    @ctf_group.command(name="scoreboard", description="Show the CTF scoreboard.")
    async def ctf_scoreboard(self, interaction: discord.Interaction):
        db = self.bot.db
        cursor = await db.execute(
            """
            SELECT s.user_id AS user_id, SUM(c.points) AS total
            FROM ctf_solves s
            JOIN ctf_challenges c ON c.id = s.challenge_id
            WHERE s.guild_id = ?
            GROUP BY s.user_id
            ORDER BY total DESC
            LIMIT 15
            """,
            (interaction.guild.id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No solves yet.")
            return

        lines = [f"{i + 1}. <@{row['user_id']}> - {row['total']} pts" for i, row in enumerate(rows)]
        embed = discord.Embed(title="CTF Scoreboard", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CTF(bot))
