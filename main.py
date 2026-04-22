import os
import json
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN")
CONFIG_FILE = "config.json"
OWNER_ID = 1025704740828491806

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


def save_user_backup(guild_id: int, user_id: int, kind: str, data: dict):
    cfg = load_config()
    g = cfg.get(str(guild_id), {})
    backups = g.get("backups", {})
    user_backups = backups.get(str(user_id), {})
    user_backups[kind] = data
    backups[str(user_id)] = user_backups
    g["backups"] = backups
    cfg[str(guild_id)] = g
    save_config(cfg)


def pop_user_backup(guild_id: int, user_id: int, kind: str):
    cfg = load_config()
    g = cfg.get(str(guild_id), {})
    backups = g.get("backups", {})
    user_backups = backups.get(str(user_id), {})
    data = user_backups.pop(kind, None)
    if user_backups:
        backups[str(user_id)] = user_backups
    else:
        backups.pop(str(user_id), None)
    g["backups"] = backups
    cfg[str(guild_id)] = g
    save_config(cfg)
    return data


def has_permission(interaction: discord.Interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    cfg = get_guild_cfg(interaction.guild.id)
    allowed = cfg.get("permission_roles", [])
    user_role_ids = {r.id for r in interaction.user.roles}
    return any(rid in user_role_ids for rid in allowed)


async def deny(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🚫 You don't have permission to use this bot.", ephemeral=True
    )


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
    if not has_permission(interaction):
        await deny(interaction)
        return
    embed = discord.Embed(
        title="✨ Moderation Bot — Help",
        description=(
            "A clean, no-nonsense moderation companion built to keep your server safe. "
            "Blacklist troublemakers, keep an eye on suspicious users with the watchlist, "
            "assign ranks, and run quick blacklist checks — all from a single tidy panel."
        ),
        color=0x00FFFF,
    )
    embed.add_field(name="🚫  /blacklist", value="Blacklist a user — strips their roles, renames them, and applies the blacklist role.", inline=False)
    embed.add_field(name="♻️  /unblacklist", value="Restore a blacklisted user — gives back their roles and nickname.", inline=False)
    embed.add_field(name="👁️  /watchlist", value="Add a user to the watchlist — keeps their roles but flags them for monitoring.", inline=False)
    embed.add_field(name="🟢  /unwatchlist", value="Remove a user from the watchlist and restore their nickname.", inline=False)
    embed.add_field(name="⚙️  /setup", value="Configure the blacklist and watchlist roles before using moderation commands.", inline=False)
    embed.add_field(name="🔑  /permission", value="Owner-only. Grant a role permission to use the bot.", inline=False)
    embed.set_footer(text="Tip: Run /setup first to configure your roles.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------- /setup ----------
SETUP_CHOICES = [
    app_commands.Choice(name="Blacklist Role", value="blacklist"),
    app_commands.Choice(name="Watchlist Role", value="watchlist"),
]


@bot.tree.command(name="setup", description="Configure the blacklist or watchlist role")
@app_commands.describe(role_type="Which role do you want to set up?", role_id="Paste the role ID here")
@app_commands.choices(role_type=SETUP_CHOICES)
async def setup_cmd(interaction: discord.Interaction, role_type: app_commands.Choice[str], role_id: str):
    if not has_permission(interaction):
        await deny(interaction)
        return
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ You need the **Manage Server** permission to use this.", ephemeral=True)
        return

    try:
        rid = int(role_id.strip())
    except ValueError:
        await interaction.response.send_message("❌ That doesn't look like a valid role ID. Right-click a role and copy its ID.", ephemeral=True)
        return

    role = interaction.guild.get_role(rid)
    if role is None:
        await interaction.response.send_message("❌ I couldn't find a role with that ID in this server.", ephemeral=True)
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
                f"⚠️ The blacklist role can still view some channels. Please disable channel access for this role first.\n\nChannels still visible: {preview}{more}",
                ephemeral=True,
            )
            return

        set_guild_cfg(interaction.guild.id, "blacklist_role", rid)
        await interaction.response.send_message("✅ **Blacklisted Command has been set**", ephemeral=True)
        return

    set_guild_cfg(interaction.guild.id, "watchlist_role", rid)
    await interaction.response.send_message("✅ **WatchList command has been set**", ephemeral=True)


# ---------- /permission ----------
@bot.tree.command(name="permission", description="Grant bot access to a role")
@app_commands.describe(role_ids="Role ID(s) to grant permission to (separate multiple with spaces)")
async def permission_cmd(interaction: discord.Interaction, role_ids: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("🚫 Only the bot owner can use this command.", ephemeral=True)
        return

    granted_roles = []
    invalid = []
    for piece in role_ids.split():
        try:
            rid = int(piece.strip())
        except ValueError:
            invalid.append(piece)
            continue
        role = interaction.guild.get_role(rid)
        if role is None:
            invalid.append(piece)
            continue
        granted_roles.append(role)

    if not granted_roles:
        await interaction.response.send_message("❌ No valid role IDs provided.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    current = set(cfg.get("permission_roles", []))
    for r in granted_roles:
        current.add(r.id)
    set_guild_cfg(interaction.guild.id, "permission_roles", list(current))

    embed = discord.Embed(
        title="✅ Permission Granted",
        description="Permission granted to " + ", ".join(r.mention for r in granted_roles),
        color=0x2ECC71,
    )
    if invalid:
        embed.add_field(name="Skipped (invalid IDs)", value=", ".join(invalid), inline=False)
    await interaction.response.send_message(embed=embed)


# ---------- /blacklist ----------
@bot.tree.command(name="blacklist", description="Blacklist a user")
@app_commands.describe(user="The user to blacklist", reason="Reason for blacklisting")
async def blacklist_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await deny(interaction)
        return
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need the **Manage Roles** permission to use this.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("blacklist_role")
    if not role_id:
        await interaction.response.send_message("❌ Blacklist role isn't configured. Run `/setup` first.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message("❌ The configured blacklist role no longer exists. Re-run `/setup`.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        original_roles = [r.id for r in user.roles if r != interaction.guild.default_role and r.id != role.id]
        original_nick = user.nick

        save_user_backup(interaction.guild.id, user.id, "blacklist", {
            "roles": original_roles,
            "nick": original_nick,
        })

        roles_to_remove = [r for r in user.roles if r != interaction.guild.default_role]
        if roles_to_remove:
            await user.remove_roles(*roles_to_remove, reason=f"Blacklisted by {interaction.user}")
        await user.add_roles(role, reason=f"Blacklisted by {interaction.user}: {reason}")
        try:
            await user.edit(nick="[BLACKLISTED]")
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to modify that user. Make sure my role is above theirs.")
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(title="🚫 BLACKLISTED", color=0xFF0000)
    embed.add_field(name="Blacklisted by", value=interaction.user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Offender", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of blacklist • {now}")
    await interaction.followup.send(embed=embed)


# ---------- /unblacklist ----------
@bot.tree.command(name="unblacklist", description="Remove a user from the blacklist")
@app_commands.describe(user="The user to unblacklist", reason="Reason for unblacklisting")
async def unblacklist_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await deny(interaction)
        return
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need the **Manage Roles** permission to use this.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("blacklist_role")
    if not role_id:
        await interaction.response.send_message("❌ Blacklist role isn't configured. Run `/setup` first.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))

    await interaction.response.defer()

    backup = pop_user_backup(interaction.guild.id, user.id, "blacklist") or {}
    saved_role_ids = backup.get("roles", [])
    saved_nick = backup.get("nick")

    try:
        if role and role in user.roles:
            await user.remove_roles(role, reason=f"Unblacklisted by {interaction.user}: {reason}")

        roles_to_restore = []
        for rid in saved_role_ids:
            r = interaction.guild.get_role(rid)
            if r is not None and r < interaction.guild.me.top_role:
                roles_to_restore.append(r)
        if roles_to_restore:
            await user.add_roles(*roles_to_restore, reason=f"Restoring roles after unblacklist by {interaction.user}")

        try:
            await user.edit(nick=saved_nick)
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to modify that user. Make sure my role is above theirs.")
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(title="♻️ UNBLACKLISTED", color=0xFFFF00)
    embed.add_field(name="UNBLACKLISTED BY", value=interaction.user.mention, inline=False)
    embed.add_field(name="REASON", value=reason, inline=False)
    embed.add_field(name="USER", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of unblacklist • {now}")
    await interaction.followup.send(embed=embed)


# ---------- /watchlist ----------
@bot.tree.command(name="watchlist", description="Add a user to the watchlist")
@app_commands.describe(user="The user to watchlist", reason="Reason for watchlisting")
async def watchlist_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await deny(interaction)
        return
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need the **Manage Roles** permission to use this.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("watchlist_role")
    if not role_id:
        await interaction.response.send_message("❌ Watchlist role isn't configured. Run `/setup` first.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message("❌ The configured watchlist role no longer exists. Re-run `/setup`.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        save_user_backup(interaction.guild.id, user.id, "watchlist", {"nick": user.nick})

        await user.add_roles(role, reason=f"Watchlisted by {interaction.user}: {reason}")
        try:
            await user.edit(nick="[WATCHLIST]")
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to modify that user. Make sure my role is above theirs.")
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


# ---------- /unwatchlist ----------
@bot.tree.command(name="unwatchlist", description="Remove a user from the watchlist")
@app_commands.describe(user="The user to unwatchlist", reason="Reason for unwatchlisting")
async def unwatchlist_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await deny(interaction)
        return
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ You need the **Manage Roles** permission to use this.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("watchlist_role")
    if not role_id:
        await interaction.response.send_message("❌ Watchlist role isn't configured. Run `/setup` first.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))

    await interaction.response.defer()

    backup = pop_user_backup(interaction.guild.id, user.id, "watchlist") or {}
    saved_nick = backup.get("nick")

    try:
        if role and role in user.roles:
            await user.remove_roles(role, reason=f"Unwatchlisted by {interaction.user}: {reason}")
        try:
            await user.edit(nick=saved_nick)
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to modify that user. Make sure my role is above theirs.")
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(title="🟢 UNWATCHLIST", color=0xFFFF00)
    embed.add_field(name="UNWATCHLIST BY", value=interaction.user.mention, inline=False)
    embed.add_field(name="REASON", value=reason, inline=False)
    embed.add_field(name="USER", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of unwatchlist • {now}")
    await interaction.followup.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is required.")
    bot.run(TOKEN)
