import discord
from discord import app_commands
from discord.ext import commands
import datetime
import os

# --- BOT SETUP ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Slash commands synced for {self.user}")

bot = MyBot()

# Dictionary to store role IDs (Note: This clears if the bot restarts on Railway)
server_config = {}

# --- COMMAND 1: /HELP (PRIVATE) ---
@bot.tree.command(name="help", description="View the bot's capabilities")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛡️ Sentinel AI | Core Protocols",
        description=(
            "I am an advanced security oversight unit. My primary directive is to "
            "monitor, restrict, and manage user access within this sector to ensure "
            "server stability and safety."
        ),
        color=discord.Color.cyan()
    )
    embed.add_field(name="📜 **Management**", value="• `/setup`: Configure security roles\n• `/rank`: Assign user status", inline=False)
    embed.add_field(name="🚫 **Security**", value="• `/blacklist`: Permanent restriction (Public)\n• `/watchlist`: Close monitoring (Public)\n• `/check`: Audit a user", inline=False)
    embed.set_footer(text="System Status: Operational • Protocol v1.0")
    
    # ephemeral=True makes this message private
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- COMMAND 2: /SETUP (PRIVATE) ---
@bot.tree.command(name="setup", description="Configure blacklist and watchlist roles")
@app_commands.describe(role_type="Which role are you setting up?", role_id="The ID of the role")
@app_commands.choices(role_type=[
    app_commands.Choice(name="Blacklist Role", value="blacklist"),
    app_commands.Choice(name="Watchlist Role", value="watchlist")
])
async def setup(interaction: discord.Interaction, role_type: str, role_id: str):
    try:
        role = interaction.guild.get_role(int(role_id))
    except ValueError:
        return await interaction.response.send_message("❌ Please provide a numeric Role ID.", ephemeral=True)
    
    if not role:
        return await interaction.response.send_message("❌ Invalid Role ID. Role not found.", ephemeral=True)

    if role_type == "blacklist":
        if role.permissions.view_channel:
            return await interaction.response.send_message("⚠️ **Setup Aborted:** The Blacklist role must have 'View Channels' turned OFF in settings first!", ephemeral=True)
        
        server_config.setdefault(interaction.guild_id, {})['blacklist'] = int(role_id)
        await interaction.user.send(f"✅ **Blacklisted Command has been set** in {interaction.guild.name}.")
    else:
        server_config.setdefault(interaction.guild_id, {})['watchlist'] = int(role_id)
        await interaction.user.send(f"✅ **WatchList command has been set** in {interaction.guild.name}.")

    await interaction.response.send_message(f"Configuration for **{role_type}** updated.", ephemeral=True)

# --- COMMAND 3: /BLACKLIST (PUBLIC) ---
@bot.tree.command(name="blacklist", description="Blacklist a user from the server")
async def blacklist(interaction: discord.Interaction, offender: discord.Member, reason: str):
    config = server_config.get(interaction.guild_id)
    if not config or 'blacklist' not in config:
        return await interaction.response.send_message("❌ Error: Setup the Blacklist role first using `/setup`!", ephemeral=True)

    role = interaction.guild.get_role(config['blacklist'])
    
    # Update user state
    await offender.edit(nick="[BLACKLISTED]", roles=[role])

    embed = discord.Embed(title="🚫 USER BLACKLISTED", color=discord.Color.red(), timestamp=datetime.datetime.now())
    embed.add_field(name="Blacklisted By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Offender", value=offender.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    # Public message (no ephemeral=True)
    await interaction.response.send_message(embed=embed)

# --- COMMAND 4: /WATCHLIST (PUBLIC) ---
@bot.tree.command(name="watchlist", description="Place a user on the watchlist")
async def watchlist(interaction: discord.Interaction, offender: discord.Member, reason: str):
    config = server_config.get(interaction.guild_id)
    if not config or 'watchlist' not in config:
        return await interaction.response.send_message("❌ Error: Setup the Watchlist role first using `/setup`!", ephemeral=True)

    role = interaction.guild.get_role(config['watchlist'])
    
    # Update user state
    await offender.edit(nick="[WATCHLIST]")
    await offender.add_roles(role)

    embed = discord.Embed(title="👀 WATCHLISTED USER", color=discord.Color.from_rgb(255, 255, 255), timestamp=datetime.datetime.now())
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Offender", value=offender.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    # Public message (no ephemeral=True)
    await interaction.response.send_message(embed=embed)

# --- START THE BOT ---
@bot.event
async def on_ready():
    print(f'System Online: {bot.user}')

bot.run(os.getenv("DISCORD_TOKEN"))
