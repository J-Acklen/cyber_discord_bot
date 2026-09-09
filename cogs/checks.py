"""Shared permission checks for restricted slash commands.

A user passes is_staff() if they have Discord's Manage Server permission OR
hold the role configured as ADMIN_ROLE_ID in .env. That second path lets club
officers run admin commands without full server Administrator.

is_ctf_admin() is narrower: it passes for staff (as above) OR anyone holding
the role configured as CTF_ADMIN_ROLE_ID, so CTF challenge management can be
delegated to specific members without giving them full staff powers.
"""

import os

import discord
from discord import app_commands

ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
CTF_ADMIN_ROLE_ID = os.getenv("CTF_ADMIN_ROLE_ID")


def _has_role(interaction: discord.Interaction, role_id_str: str) -> bool:
    if not role_id_str:
        return False
    role_id = int(role_id_str)
    return any(r.id == role_id for r in interaction.user.roles)


def is_staff():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        if _has_role(interaction, ADMIN_ROLE_ID):
            return True
        raise app_commands.CheckFailure(
            "You need the Manage Server permission or the configured staff role to use this command."
        )

    return app_commands.check(predicate)


def is_ctf_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        if _has_role(interaction, ADMIN_ROLE_ID):
            return True
        if _has_role(interaction, CTF_ADMIN_ROLE_ID):
            return True
        raise app_commands.CheckFailure(
            "You need the Manage Server permission, the configured staff role, or the CTF Admin role to use this command."
        )

    return app_commands.check(predicate)
