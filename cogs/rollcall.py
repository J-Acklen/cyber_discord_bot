"""Roll call / accountability: staff post a roll call, members react to check
themselves in, and staff can pull a report of who's missing. Pairs naturally
with /rolelink for units that track personnel (e.g. an S-1 role).
"""

import discord
from discord import app_commands
from discord.ext import commands

from .checks import is_staff

PRESENT_EMOJI = "✅"  # ✅
EXCUSED_EMOJI = "\U0001F7E1"  # 🟡


class RollCall(commands.Cog):
    rollcall_group = app_commands.Group(name="rollcall", description="Accountability check-ins")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @rollcall_group.command(name="start", description="Post a roll call for members to check into.")
    @app_commands.describe(
        title="What this roll call is for, e.g. 'Tuesday meeting'",
        required_role="If set, /rollcall report will list members with this role who haven't checked in",
    )
    @is_staff()
    async def rollcall_start(self, interaction: discord.Interaction, title: str, required_role: discord.Role = None):
        embed = discord.Embed(
            title=f"Roll Call: {title}",
            description=f"React {PRESENT_EMOJI} if you're present, {EXCUSED_EMOJI} if you're excused.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Started by {interaction.user}")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction(PRESENT_EMOJI)
        await message.add_reaction(EXCUSED_EMOJI)

        db = self.bot.db
        await db.execute(
            "INSERT INTO rollcalls (guild_id, channel_id, message_id, title, required_role_id, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                interaction.guild.id,
                interaction.channel.id,
                message.id,
                title,
                required_role.id if required_role else None,
                interaction.user.id,
            ),
        )
        await db.commit()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, adding=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_reaction(payload, adding=False)

    async def _handle_reaction(self, payload: discord.RawReactionActionEvent, adding: bool):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) not in (PRESENT_EMOJI, EXCUSED_EMOJI):
            return

        db = self.bot.db
        cursor = await db.execute(
            "SELECT id, is_open FROM rollcalls WHERE message_id = ?",
            (payload.message_id,),
        )
        rollcall = await cursor.fetchone()
        if not rollcall or not rollcall["is_open"]:
            return

        status = "present" if str(payload.emoji) == PRESENT_EMOJI else "excused"

        if adding:
            await db.execute(
                "INSERT INTO rollcall_responses (rollcall_id, user_id, status) VALUES (?, ?, ?) "
                "ON CONFLICT (rollcall_id, user_id) DO UPDATE SET status = excluded.status, responded_at = datetime('now')",
                (rollcall["id"], payload.user_id, status),
            )
        else:
            await db.execute(
                "DELETE FROM rollcall_responses WHERE rollcall_id = ? AND user_id = ? AND status = ?",
                (rollcall["id"], payload.user_id, status),
            )
        await db.commit()

    @rollcall_group.command(name="report", description="See who has and hasn't checked into a roll call.")
    @app_commands.describe(rollcall_id="The roll call's ID (shown when you ran /rollcall start, or from /rollcall list)")
    @is_staff()
    async def rollcall_report(self, interaction: discord.Interaction, rollcall_id: int):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT * FROM rollcalls WHERE id = ? AND guild_id = ?",
            (rollcall_id, interaction.guild.id),
        )
        rollcall = await cursor.fetchone()
        if not rollcall:
            await interaction.response.send_message(f"No roll call with ID `{rollcall_id}`.", ephemeral=True)
            return

        cursor = await db.execute(
            "SELECT user_id, status FROM rollcall_responses WHERE rollcall_id = ?",
            (rollcall_id,),
        )
        responses = await cursor.fetchall()
        present = [r["user_id"] for r in responses if r["status"] == "present"]
        excused = [r["user_id"] for r in responses if r["status"] == "excused"]

        embed = discord.Embed(title=f"Roll Call Report: {rollcall['title']}", color=discord.Color.blurple())
        embed.add_field(name=f"Present ({len(present)})", value=" ".join(f"<@{u}>" for u in present) or "None", inline=False)
        embed.add_field(name=f"Excused ({len(excused)})", value=" ".join(f"<@{u}>" for u in excused) or "None", inline=False)

        if rollcall["required_role_id"]:
            role = interaction.guild.get_role(rollcall["required_role_id"])
            if role:
                responded = set(present) | set(excused)
                missing = [m for m in role.members if m.id not in responded]
                value = " ".join(m.mention for m in missing) if missing else "Everyone has checked in \U0001F389"
                embed.add_field(name=f"Missing from {role.name} ({len(missing)})", value=value, inline=False)

        await interaction.response.send_message(embed=embed)

    @rollcall_group.command(name="close", description="Close a roll call so reactions stop counting.")
    @app_commands.describe(rollcall_id="The roll call's ID")
    @is_staff()
    async def rollcall_close(self, interaction: discord.Interaction, rollcall_id: int):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT * FROM rollcalls WHERE id = ? AND guild_id = ?",
            (rollcall_id, interaction.guild.id),
        )
        rollcall = await cursor.fetchone()
        if not rollcall:
            await interaction.response.send_message(f"No roll call with ID `{rollcall_id}`.", ephemeral=True)
            return

        await db.execute("UPDATE rollcalls SET is_open = 0 WHERE id = ?", (rollcall_id,))
        await db.commit()

        channel = interaction.guild.get_channel(rollcall["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(rollcall["message_id"])
                embed = message.embeds[0]
                embed.color = discord.Color.dark_gray()
                embed.description = "This roll call is closed. Reactions no longer count."
                await message.edit(embed=embed)
            except discord.NotFound:
                pass

        await interaction.response.send_message(f"Closed roll call `{rollcall_id}`.")

    @rollcall_group.command(name="list", description="List recent roll calls and their IDs.")
    @is_staff()
    async def rollcall_list(self, interaction: discord.Interaction):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT id, title, is_open, created_at FROM rollcalls WHERE guild_id = ? ORDER BY id DESC LIMIT 10",
            (interaction.guild.id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No roll calls yet.")
            return

        lines = [f"`{r['id']}` - {r['title']} ({'open' if r['is_open'] else 'closed'}, {r['created_at']})" for r in rows]
        embed = discord.Embed(title="Recent Roll Calls", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RollCall(bot))
