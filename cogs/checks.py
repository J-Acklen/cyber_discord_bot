"""Shared permission check for admin-only slash commands.

A user passes if they have Discord's Administrator/Manage Guild style perms
OR hold the role configured as ADMIN_ROLE_ID in .env. That second path lets
club officers run admin commands without full server Administrator.
"""

import os

import discord
from discord import app_commands

ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")


def is_staff():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        if ADMIN_ROLE_ID:
            role_id = int(ADMIN_ROLE_ID)
            if any(r.id == role_id for r in interaction.user.roles):
                return True
        raise app_commands.CheckFailure(
            "You need the Manage Server permission or the configured staff role to use this command."
        )

    return app_commands.check(predicate)
