import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="userinfo", description="Show info about a member.")
    @app_commands.describe(member="The member to look up (defaults to you)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed = discord.Embed(title=str(member), color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "R"))
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        embed.add_field(name="Roles", value=" ".join(roles) if roles else "None", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Show info about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=guild.name)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Roles", value=len(guild.roles))
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="roleinfo", description="Show info about a role.")
    @app_commands.describe(role="The role to look up")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=role.name, color=role.color)
        embed.add_field(name="Members with role", value=len(role.members))
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Mentionable", value=str(role.mentionable))
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a member's avatar.")
    @app_commands.describe(member="The member to look up (defaults to you)")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"{member}'s avatar")
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="commands", description="List all available commands (visible only to you).")
    async def commands_list(self, interaction: discord.Interaction):
        section_titles = {
            "Moderation": "Moderation \U0001F6E1️",
            "Utility": "Utility",
            "AutoRole": "Role Linking",
            "CTF": "CTF Tracker",
            "RollCall": "Roll Call",
            "Resources": "Resource Library",
        }

        embed = discord.Embed(
            title="Available Commands",
            description="\U0001F512 = staff only (Manage Server permission or the configured staff role).",
            color=discord.Color.blurple(),
        )

        for cog_name, cog in self.bot.cogs.items():
            app_cmds = cog.get_app_commands()
            if not app_cmds:
                continue

            lines = []
            for cmd in app_cmds:
                if isinstance(cmd, app_commands.Group):
                    for sub in cmd.commands:
                        lock = "\U0001F512 " if sub.checks else ""
                        lines.append(f"{lock}`/{cmd.name} {sub.name}` - {sub.description}")
                else:
                    lock = "\U0001F512 " if cmd.checks else ""
                    lines.append(f"{lock}`/{cmd.name}` - {cmd.description}")

            embed.add_field(name=section_titles.get(cog_name, cog_name), value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
