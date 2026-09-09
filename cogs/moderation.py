from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from .checks import is_staff


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="Why they're being kicked")
    @is_staff()
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"Kicked {member.mention}. Reason: {reason}")

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="The member to ban", reason="Why they're being banned")
    @is_staff()
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.ban(reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"Banned {member.mention}. Reason: {reason}")

    @app_commands.command(name="unban", description="Unban a user by ID.")
    @app_commands.describe(user_id="The Discord user ID to unban")
    @is_staff()
    async def unban(self, interaction: discord.Interaction, user_id: str):
        user = discord.Object(id=int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"Unbanned user ID {user_id}.")

    @app_commands.command(name="timeout", description="Timeout (mute) a member for a number of minutes.")
    @app_commands.describe(member="The member to timeout", minutes="Duration in minutes (max 40320 = 28 days, Discord's limit)", reason="Why they're being timed out")
    @is_staff()
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
        duration = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"{interaction.user}: {reason}")
        await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minute(s). Reason: {reason}")

    @app_commands.command(name="untimeout", description="Remove an active timeout from a member.")
    @app_commands.describe(member="The member to un-timeout")
    @is_staff()
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None, reason=f"Timeout removed by {interaction.user}")
        await interaction.response.send_message(f"Removed timeout from {member.mention}.")

    @app_commands.command(name="warn", description="Log a warning against a member.")
    @app_commands.describe(member="The member to warn", reason="Why they're being warned")
    @is_staff()
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        db = self.bot.db
        await db.execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason) VALUES (?, ?, ?, ?)",
            (interaction.guild.id, member.id, interaction.user.id, reason),
        )
        await db.commit()
        await interaction.response.send_message(f"Warned {member.mention}. Reason: {reason}")

    @app_commands.command(name="warnings", description="List warnings for a member.")
    @app_commands.describe(member="The member to look up")
    @is_staff()
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT reason, moderator_id, created_at FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
            (interaction.guild.id, member.id),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message(f"{member.mention} has no warnings.")
            return

        lines = [f"- {row['created_at']} by <@{row['moderator_id']}>: {row['reason']}" for row in rows]
        embed = discord.Embed(title=f"Warnings for {member}", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="The member whose warnings will be cleared")
    @is_staff()
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        db = self.bot.db
        await db.execute(
            "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
            (interaction.guild.id, member.id),
        )
        await db.commit()
        await interaction.response.send_message(f"Cleared warnings for {member.mention}.")

    @app_commands.command(name="purge", description="Bulk delete recent messages in this channel.")
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    @is_staff()
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Deleted {len(deleted)} message(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
