import os
import json
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN")
CONFIG_FILE = "config.json"

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- Config helpers ----------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_cfg(guild_id: int):
    cfg = load_config()
    return cfg.get(str(guild_id), {})


def set_guild_cfg(guild_id: int, key: str, value):
    cfg = load_config()
    g = cfg.get(str(guild_id), {})
    g[key] = value
    cfg[str(guild_id)] = g
    save_config(cfg)


# ---------- Events ----------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user} | Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")


# ---------- /help ----------
@bot.tree.command(name="help", description="Shows what this bot can do")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ Moderation Bot — Help",
        description=(
            "A clean, no-nonsense moderation companion built to keep your server safe. "
            "Blacklist troublemakers, keep an eye on suspicious users with the watchlist, "
            "assign ranks, and run quick blacklist checks — all from a single tidy panel."
        ),
        color=0x00FFFF,
    )
    embed.add_field(
        name="🚫  /blacklist",
        value="Blacklist a user — strips their roles, renames them, and applies the blacklist role.",
        inline=False,
    )
    embed.add_field(
        name="👁️  /watchlist",
        value="Add a user to the watchlist — keeps their roles but flags them for monitoring.",
        inline=False,
    )
    embed.add_field(
        name="🎖️  Assign Rank",
        value="Quickly grant a rank/role to a member.",
        inline=False,
    )
    embed.add_field(
        name="🔍  Blacklist Check",
        value="Check whether a user is currently blacklisted.",
        inline=False,
    )
    embed.add_field(
        name="⚙️  /setup",
        value="Configure the blacklist and watchlist roles before using moderation commands.",
        inline=False,
    )
    embed.set_footer(text="Tip: Run /setup first to configure your roles.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------- /setup ----------
SETUP_CHOICES = [
    app_commands.Choice(name="Blacklist Role", value="blacklist"),
    app_commands.Choice(name="Watchlist Role", value="watchlist"),
]


@bot.tree.command(name="setup", description="Configure the blacklist or watchlist role")
@app_commands.describe(
    role_type="Which role do you want to set up?",
    role_id="Paste the role ID here",
)
@app_commands.choices(role_type=SETUP_CHOICES)
async def setup_cmd(
    interaction: discord.Interaction,
    role_type: app_commands.Choice[str],
    role_id: str,
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ You need the **Manage Server** permission to use this.",
            ephemeral=True,
        )
        return

    try:
        rid = int(role_id.strip())
    except ValueError:
        await interaction.response.send_message(
            "❌ That doesn't look like a valid role ID. Right-click a role and copy its ID.",
            ephemeral=True,
        )
        return

    role = interaction.guild.get_role(rid)
    if role is None:
        await interaction.response.send_message(
            "❌ I couldn't find a role with that ID in this server.",
            ephemeral=True,
        )
        return

    if role_type.value == "blacklist":
        bad_channels = []
        for ch in interaction.guild.channels:
            try:
                overwrite = ch.overwrites_for(role)
                if overwrite.view_channel is True:
                    bad_channels.append(ch.name)
                    continue
                perms = ch.permissions_for(role) if hasattr(ch, "permissions_for") else None
                if perms and perms.view_channel:
                    bad_channels.append(ch.name)
            except Exception:
                continue

        if bad_channels:
            preview = ", ".join(f"#{c}" for c in bad_channels[:10])
            more = f" (+{len(bad_channels) - 10} more)" if len(bad_channels) > 10 else ""
            await interaction.response.send_message(
                "⚠️ The blacklist role can still view some channels. "
                f"Please disable channel access for this role first.\n\n"
                f"Channels still visible: {preview}{more}",
                ephemeral=True,
            )
            return

        set_guild_cfg(interaction.guild.id, "blacklist_role", rid)
        await interaction.response.send_message(
            "✅ **Blacklisted Command has been set**", ephemeral=True
        )
        return

    set_guild_cfg(interaction.guild.id, "watchlist_role", rid)
    await interaction.response.send_message(
        "✅ **WatchList command has been set**", ephemeral=True
    )


# ---------- /blacklist ----------
@bot.tree.command(name="blacklist", description="Blacklist a user")
@app_commands.describe(user="The user to blacklist", reason="Reason for blacklisting")
async def blacklist_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str,
):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "❌ You need the **Manage Roles** permission to use this.", ephemeral=True
        )
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("blacklist_role")
    if not role_id:
        await interaction.response.send_message(
            "❌ Blacklist role isn't configured. Run `/setup` first.", ephemeral=True
        )
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message(
            "❌ The configured blacklist role no longer exists. Re-run `/setup`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    try:
        roles_to_remove = [r for r in user.roles if r != interaction.guild.default_role]
        if roles_to_remove:
            await user.remove_roles(*roles_to_remove, reason=f"Blacklisted by {interaction.user}")
        await user.add_roles(role, reason=f"Blacklisted by {interaction.user}: {reason}")
        try:
            await user.edit(nick="[BLACKLISTED]")
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to modify that user. Make sure my role is above theirs."
        )
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title="🚫 BLACKLISTED",
        color=0xFF0000,
    )
    embed.add_field(name="Blacklisted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Offender", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of blacklist • {now}")
    await interaction.followup.send(embed=embed)


# ---------- /watchlist ----------
@bot.tree.command(name="watchlist", description="Add a user to the watchlist")
@app_commands.describe(user="The user to watchlist", reason="Reason for watchlisting")
async def watchlist_cmd(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str,
):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message(
            "❌ You need the **Manage Roles** permission to use this.", ephemeral=True
        )
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("watchlist_role")
    if not role_id:
        await interaction.response.send_message(
            "❌ Watchlist role isn't configured. Run `/setup` first.", ephemeral=True
        )
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message(
            "❌ The configured watchlist role no longer exists. Re-run `/setup`.",
            ephemeral=True,
        )
        return

    await interaction.response.defer()

    try:
        await user.add_roles(role, reason=f"Watchlisted by {interaction.user}: {reason}")
        try:
            await user.edit(nick="[WATCHLIST]")
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to modify that user. Make sure my role is above theirs."
        )
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title="👁️ WATCHLISTED USER",
        description=f"USER HAS BEEN WATCHLISTED BY {interaction.user.mention}",
        color=0xFFFFFF,
    )
    embed.add_field(name="REASON", value=reason, inline=False)
    embed.add_field(name="OFFENDER", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of watchlist • {now}")
    await interaction.followup.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is required.")
    bot.run(TOKEN)
        if not has_permission(interaction):
        await deny(interaction)
        return
            async def help_cmd(interaction: discord.Interaction):
    if not has_permission(interaction):
        await deny(interaction)
        return
    embed = discord.Embed(
        ...
