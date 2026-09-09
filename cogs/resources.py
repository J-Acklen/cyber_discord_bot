"""Resource library: a shared, searchable catalog of tools, writeups,
TryHackMe/HTB rooms, and reference links the unit collects over time.
Staff curate entries (add/remove); everyone can search and browse.
"""

import discord
from discord import app_commands
from discord.ext import commands

from .checks import is_staff


class Resources(commands.Cog):
    resource_group = app_commands.Group(name="resource", description="Shared library of tools, writeups, and links")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @resource_group.command(name="add", description="Add a link to the shared resource library.")
    @app_commands.describe(title="Short name for the resource", url="The link", category="e.g. web, crypto, forensics, tool, writeup")
    @is_staff()
    async def resource_add(self, interaction: discord.Interaction, title: str, url: str, category: str):
        if not url.startswith(("http://", "https://")):
            await interaction.response.send_message("That doesn't look like a valid URL - include http(s)://", ephemeral=True)
            return

        db = self.bot.db
        cursor = await db.execute(
            "INSERT INTO resources (guild_id, title, url, category, added_by) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild.id, title, url, category.lower(), interaction.user.id),
        )
        await db.commit()
        await interaction.response.send_message(f"Added **{title}** (`{category.lower()}`) - #{cursor.lastrowid}")

    @resource_group.command(name="search", description="Search the resource library by keyword.")
    @app_commands.describe(query="Matches against title and category")
    async def resource_search(self, interaction: discord.Interaction, query: str):
        db = self.bot.db
        like = f"%{query}%"
        cursor = await db.execute(
            "SELECT id, title, url, category FROM resources WHERE guild_id = ? "
            "AND (title LIKE ? OR category LIKE ?) ORDER BY category, title LIMIT 20",
            (interaction.guild.id, like, like),
        )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message(f"No resources matching `{query}`.")
            return

        lines = [f"**[{r['title']}]({r['url']})** - `{r['category']}` (#{r['id']})" for r in rows]
        embed = discord.Embed(title=f"Resources matching \"{query}\"", description="\n".join(lines))
        await interaction.response.send_message(embed=embed)

    @resource_group.command(name="list", description="List resources, optionally filtered by category.")
    @app_commands.describe(category="Only show this category (optional)")
    async def resource_list(self, interaction: discord.Interaction, category: str = None):
        db = self.bot.db
        if category:
            cursor = await db.execute(
                "SELECT id, title, url, category FROM resources WHERE guild_id = ? AND category = ? "
                "ORDER BY title LIMIT 25",
                (interaction.guild.id, category.lower()),
            )
        else:
            cursor = await db.execute(
                "SELECT id, title, url, category FROM resources WHERE guild_id = ? ORDER BY category, title LIMIT 25",
                (interaction.guild.id,),
            )
        rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No resources found." + (f" (category: `{category}`)" if category else ""))
            return

        lines = [f"**[{r['title']}]({r['url']})** - `{r['category']}` (#{r['id']})" for r in rows]
        embed = discord.Embed(title="Resource Library", description="\n".join(lines))
        if len(rows) == 25:
            embed.set_footer(text="Showing first 25 - use /resource search to narrow it down.")
        await interaction.response.send_message(embed=embed)

    @resource_group.command(name="remove", description="Remove a resource by its ID.")
    @app_commands.describe(resource_id="The ID shown next to a resource in /resource list or /resource search")
    @is_staff()
    async def resource_remove(self, interaction: discord.Interaction, resource_id: int):
        db = self.bot.db
        cursor = await db.execute(
            "SELECT title FROM resources WHERE id = ? AND guild_id = ?",
            (resource_id, interaction.guild.id),
        )
        row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message(f"No resource with ID `{resource_id}`.", ephemeral=True)
            return

        await db.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
        await db.commit()
        await interaction.response.send_message(f"Removed **{row['title']}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Resources(bot))
