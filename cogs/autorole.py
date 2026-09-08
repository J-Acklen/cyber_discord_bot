"""Linked roles: when a member is given a configured "trigger" role, the bot
automatically adds the configured "linked" role too (e.g. giving someone
"S-1" auto-grants "Staff Officer"). Configure links with /rolelink commands.
"""

import discord
from discord import app_commands
from discord.ext import commands

from .checks import is_staff

class AutoRole(commands.Cog):
    rolelink_group = app_commands.Group(name="rolelink", description="Manage automatic role-on-role assignments")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        added_roles = set(after.roles) - set(before.roles)
        if not added_roles:
            return

        db = self.bot.db
        for role in added_roles:
            cursor = await db.execute(
                "SELECT linked_role_id FROM role_links WHERE guild_id = ? AND trigger_role_id = ?",
                (after.guild.id, role.id),
            )
            rows = await cursor.fetchall()
            for row in rows:
                linked_role = after.guild.get_role(row["linked_role_id"])
                if linked_role and linked_role not in after.roles:
                    await after.add_roles(linked_role, reason=f"Auto-linked from role {role.name}")

    @rolelink_group.command(name="add", description="When a member gets trigger_role, automatically also give them linked_role.")
    @app_commands.describe(trigger_role="The role that triggers the assignment", linked_role="The role to auto-assign")
    @is_staff()
    async def rolelink_add(self, interaction: discord.Interaction, trigger_role: discord.Role, linked_role: discord.Role):
        if trigger_role.id == linked_role.id:
            await interaction.response.send_message("Trigger role and linked role can't be the same.", ephemeral=True)
            return

        db = self.bot.db
        await db.execute(
            "INSERT OR IGNORE INTO role_links (guild_id, trigger_role_id, linked_role_id) VALUES (?, ?, ?)",
            (interaction.guild.id, trigger_role.id, linked_role.id),
        )
        await db.commit()
        await interaction.response.send_message(
            f"Members given {trigger_role.mention} will now also receive {linked_role.mention}."
        )

    @rolelink_group.command(name="remove", description="Remove a role link.")
    @app_commands.describe(trigger_role="The trigger role", linked_role="The linked role")
    @is_staff()
    async def rolelink_remove(self, interaction: discord.Interaction, trigger_role: discord.Role, linked_role: discord.Role):
        db = self.bot.db
        await db.execute(
            "DELETE FROM role_links WHERE guild_id = ? AND trigger_role_id = ? AND linked_role_id = ?",
            (interaction.guild.id, trigger_role.id, linked_role.id),
        )
        await db.commit()
        await interaction.response.send_message(f"Removed link: {trigger_role.mention} -> {linked_role.mention}.")

    @rolelink_group.command(name="list", description="List all configured role links.")
    @is_staff()
    async def rolelink_list(self, interaction: discord.Interaction):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT trigger_role_id, linked_role_id FROM role_links WHERE guild_id = ?",
            (interaction.guild.id,),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No role links configured.")
            return

        lines = [f"<@&{row['trigger_role_id']}> -> <@&{row['linked_role_id']}>" for row in rows]
        embed = discord.Embed(title="Role Links", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRole(bot))
