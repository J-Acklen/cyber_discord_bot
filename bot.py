import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import database

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

INTENTS = discord.Intents.default()
INTENTS.members = True  # required for role-link auto-assignment and moderation lookups
INTENTS.message_content = False  # not needed; everything here is slash commands

COGS = [
    "cogs.moderation",
    "cogs.utility",
    "cogs.autorole",
    "cogs.ctf",
    "cogs.rollcall",
    "cogs.resources",
    "cogs.pwncollege",
]


class CyberUnitBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)
        self.db = None

    async def setup_hook(self):
        self.db = await database.connect()

        for cog in COGS:
            await self.load_extension(cog)
            log.info("Loaded %s", cog)

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Synced %d commands to guild %s", len(synced), GUILD_ID)
        else:
            synced = await self.tree.sync()
            log.info("Synced %d commands globally", len(synced))

    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()


bot = CyberUnitBot()


@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        message = f"Slow down - try again in {error.retry_after:.1f}s."
    elif isinstance(error, discord.app_commands.CheckFailure):
        message = str(error) or "You don't have permission to use this command."
    else:
        log.exception("Unhandled app command error", exc_info=error)
        message = "Something went wrong running that command."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


async def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
