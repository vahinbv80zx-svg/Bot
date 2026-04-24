import os
import json
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN")
OWNER_ID = 1025704740828491806
CONFIG_FILE = "config.json"
LB_FILE = "leaderboards.json"

# --- FIXED IMAGE URLS ---
HEADER_GIF = "https://cdn.discordapp.com/attachments/1496355649502580757/1496377599662755931/WHITE-1.gif?ex=69e9a9bd&is=69e8583d&hm=cae7913688d5a686d7d1da1248509c23b11bacf17387fef4a9d546e6ae9874a7&"
VACANT_THUMB = "https://cdn.discordapp.com/attachments/1496355649502580757/1496377629501030400/Black_question_mark.png?ex=69e9a9c4&is=69e85844&hm=c5f1e8c59fb5aff7c11f84e43133b22c7785163c20b0c150b5caf04095e32eb6&"

# Brand colors for styled responses
COLOR_PRIMARY = 0x5865F2   # Discord blurple
COLOR_SUCCESS = 0x57F287   # green
COLOR_ERROR   = 0xED4245   # red
COLOR_WARN    = 0xFEE75C   # yellow
COLOR_INFO    = 0x00FFFF   # cyan

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- Helper Functions ----------
def _load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_guild_cfg(guild_id):
    return _load(CONFIG_FILE).get(str(guild_id), {})

def set_guild_cfg(guild_id, key, value):
    cfg = _load(CONFIG_FILE)
    g = cfg.get(str(guild_id), {})
    g[key] = value
    cfg[str(guild_id)] = g
    _save(CONFIG_FILE, cfg)

def get_lb(guild_id):
    return _load(LB_FILE).get(str(guild_id))

def set_lb(guild_id, data):
    lbs = _load(LB_FILE)
    lbs[str(guild_id)] = data
    _save(LB_FILE, lbs)

def has_permission(interaction):
    if interaction.user.id == OWNER_ID:
        return True
    cfg = get_guild_cfg(interaction.guild.id)
    # ✅ NEW: provoked mode check
    if cfg.get("provoked", False):
        return False
    allowed = cfg.get("permission_roles", [])
    return any(r.id in allowed for r in interaction.user.roles)
    
def vacant_spot(num):
    return {
        "num": num, "username": "Vacant", "discord": "Vacant",
        "roblox": "Information", "country": "Null", "stage": "Null",
        "thumbnail": VACANT_THUMB, "vacant": True,
    }

# ---------- Styled response helpers ----------
def styled_embed(title: str, description: str, color: int) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Moderation & Leaderboard System")
    return e

def error_embed(description: str, title: str = "✖  Access Denied") -> discord.Embed:
    return styled_embed(title, description, COLOR_ERROR)

def warn_embed(description: str, title: str = "⚠  Heads Up") -> discord.Embed:
    return styled_embed(title, description, COLOR_WARN)

def success_embed(description: str, title: str = "✓  Success") -> discord.Embed:
    return styled_embed(title, description, COLOR_SUCCESS)

def info_embed(description: str, title: str = "ℹ  Info") -> discord.Embed:
    return styled_embed(title, description, COLOR_INFO)


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
        title="✨  Moderation & Leaderboard Bot",
        description=(
            "A clean, all-in-one toolkit for keeping your server tidy "
            "and running a polished leaderboard with up to **50 spots**."
        ),
        color=COLOR_PRIMARY,
    )
    embed.add_field(name="⚙️  /setup", value="Configure the blacklist or watchlist role.", inline=False)
    embed.add_field(name="🔑  /permission", value="*Owner only.* Grant a role access to mod & leaderboard commands.", inline=False)
    embed.add_field(name="🚫  /blacklist  •  /unblacklist", value="Strip a user's roles & flag them — or remove them from the blacklist.", inline=False)
    embed.add_field(name="👁️  /watchlist  •  /unwatchlist", value="Quietly flag a user for monitoring — or clear the flag.", inline=False)
    embed.add_field(name="🏆  /createlb", value="Build a new leaderboard. Use a range like `1-10`.", inline=False)
    embed.add_field(name="✏️  /fillspot", value="Fill in a player's info on a spot.", inline=False)
    embed.add_field(name="⬆️  /moveup  •  ⬇️  /movedown", value="Swap a player with the spot above or below.", inline=False)
    embed.add_field(name="❌  /removeplayer", value="Reset a spot back to Vacant.", inline=False)
    embed.set_footer(text="Tip: Run /setup first, then /permission to give roles access.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------- /setup ----------
SETUP_CHOICES = [
    app_commands.Choice(name="Blacklist Role", value="blacklist"),
    app_commands.Choice(name="Watchlist Role", value="watchlist"),
]

@bot.tree.command(name="setup", description="Configure the blacklist or watchlist role")
@app_commands.describe(role_type="Which role to configure", role_id="Paste the role ID")
@app_commands.choices(role_type=SETUP_CHOICES)
async def setup_cmd(interaction, role_type: app_commands.Choice[str], role_id: str):
    if not has_permission(interaction):
        await interaction.response.send_message(
            embed=error_embed("You don't have permission to use this command."),
            ephemeral=True,
        )
        return
    try:
        rid = int(role_id.strip())
    except ValueError:
        await interaction.response.send_message(
            embed=error_embed("That doesn't look like a valid role ID.\nRight-click a role and copy its ID.", title="✖  Invalid Input"),
            ephemeral=True,
        )
        return
    role = interaction.guild.get_role(rid)
    if role is None:
        await interaction.response.send_message(
            embed=error_embed("I couldn't find a role with that ID in this server.", title="✖  Role Not Found"),
            ephemeral=True,
        )
        return

    if role_type.value == "blacklist":
        bad = []
        for ch in interaction.guild.channels:
            try:
                ow = ch.overwrites_for(role)
                if ow.view_channel is True:
                    bad.append(ch.name); continue
                perms = ch.permissions_for(role) if hasattr(ch, "permissions_for") else None
                if perms and perms.view_channel:
                    bad.append(ch.name)
            except Exception:
                continue
        if bad:
            preview = ", ".join(f"#{c}" for c in bad[:10])
            more = f"  *(+{len(bad)-10} more)*" if len(bad) > 10 else ""
            await interaction.response.send_message(
                embed=warn_embed(
                    f"The blacklist role can still view some channels. "
                    f"Disable channel access for this role first.\n\n**Visible:** {preview}{more}"
                ),
                ephemeral=True,
            )
            return
        set_guild_cfg(interaction.guild.id, "blacklist_role", rid)
        await interaction.response.send_message(
            embed=success_embed(f"Blacklist role set to {role.mention}."),
            ephemeral=True,
        )
        return

    set_guild_cfg(interaction.guild.id, "watchlist_role", rid)
    await interaction.response.send_message(
        embed=success_embed(f"Watchlist role set to {role.mention}."),
        ephemeral=True,
    )


# ---------- /permission ----------
@bot.tree.command(name="permission", description="Owner only. Allow a role to use mod/lb commands.")
@app_commands.describe(role="Role allowed to use commands")
async def permission_cmd(interaction: discord.Interaction, role: discord.Role):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            embed=error_embed("This command is restricted to the bot owner.", title="✖  Owner Only"),
            ephemeral=True,
        )
        return
    cfg = get_guild_cfg(interaction.guild.id)
    roles = cfg.get("permission_roles", [])
    if role.id in roles:
        roles.remove(role.id)
        emb = success_embed(f"Removed {role.mention} from allowed roles.", title="✓  Permission Revoked")
    else:
        roles.append(role.id)
        emb = success_embed(f"Granted {role.mention} access to mod & leaderboard commands.", title="✓  Permission Granted")
    set_guild_cfg(interaction.guild.id, "permission_roles", roles)
    await interaction.response.send_message(embed=emb, ephemeral=True)


# ---------- /blacklist ----------
@bot.tree.command(name="blacklist", description="Blacklist a user")
@app_commands.describe(user="User", reason="Reason")
async def blacklist_cmd(interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await interaction.response.send_message(embed=error_embed("You don't have permission to use this command."), ephemeral=True)
        return

    cfg = _load(CONFIG_FILE)
    gid = str(interaction.guild.id)
    g = cfg.get(gid, {})

    rid = g.get("blacklist_role")
    if not rid:
        await interaction.response.send_message(embed=warn_embed("Blacklist role isn't configured. Run `/setup` first."), ephemeral=True)
        return

    role = interaction.guild.get_role(int(rid))

    # ✅ SAVE ROLES
    saved_roles = [r.id for r in user.roles if r != interaction.guild.default_role]
    g.setdefault("saved_roles", {})[str(user.id)] = saved_roles
    cfg[gid] = g
    _save(CONFIG_FILE, cfg)

    await interaction.response.defer()

    try:
        await user.remove_roles(*[r for r in user.roles if r != interaction.guild.default_role])
        await user.add_roles(role, reason=f"Blacklisted by {interaction.user}: {reason}")
    except discord.Forbidden:
        await interaction.followup.send(embed=error_embed("I'm missing permissions on that user."))
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    embed = discord.Embed(title="🚫  BLACKLISTED", color=COLOR_ERROR)
    embed.add_field(name="Blacklisted by", value=interaction.user.mention)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Time • {now}")

    await interaction.followup.send(embed=embed)


# ---------- /unblacklist ----------
@bot.tree.command(name="unblacklist", description="Remove a user from blacklist")
@app_commands.describe(user="User", reason="Reason")
async def unblacklist_cmd(interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await interaction.response.send_message(
            embed=error_embed("You don't have permission to use this command."),
            ephemeral=True
        )
        return

    cfg = _load(CONFIG_FILE)
    gid = str(interaction.guild.id)
    g = cfg.get(gid, {})

    rid = g.get("blacklist_role")
    if not rid:
        await interaction.response.send_message(
            embed=warn_embed("Blacklist role isn't configured. Run `/setup` first."),
            ephemeral=True
        )
        return

    role = interaction.guild.get_role(int(rid))

    # REMOVE BLACKLIST ROLE
    if role and role in user.roles:
        try:
            await user.remove_roles(role, reason=f"Unblacklisted by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(embed=error_embed("Missing permissions."), ephemeral=True)
            return

    # ✅ RESTORE ROLES
    saved = g.get("saved_roles", {}).get(str(user.id), [])
    roles_to_restore = []

    for r_id in saved:
        r = interaction.guild.get_role(r_id)
        if r:
            roles_to_restore.append(r)

    if roles_to_restore:
        try:
            await user.add_roles(*roles_to_restore, reason="Restoring roles after unblacklist")
        except discord.Forbidden:
            pass

    # REMOVE SAVED DATA
    if "saved_roles" in g and str(user.id) in g["saved_roles"]:
        del g["saved_roles"][str(user.id)]
        cfg[gid] = g
        _save(CONFIG_FILE, cfg)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    embed = discord.Embed(title="UNBLACKLISTED", color=COLOR_SUCCESS)
    embed.add_field(name="UNBLACKLISTED BY", value=interaction.user.mention, inline=False)
    embed.add_field(name="REASON", value=reason, inline=False)
    embed.add_field(name="USER", value=user.mention, inline=False)
    embed.add_field(name="TIME", value=now, inline=False)

    await interaction.response.send_message(embed=embed)


# ---------- /watchlist ----------
@bot.tree.command(name="watchlist", description="Add a user to the watchlist")
@app_commands.describe(user="User", reason="Reason")
async def watchlist_cmd(interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await interaction.response.send_message(embed=error_embed("You don't have permission to use this command."), ephemeral=True); return
    rid = get_guild_cfg(interaction.guild.id).get("watchlist_role")
    if not rid:
        await interaction.response.send_message(embed=warn_embed("Watchlist role isn't configured. Run `/setup` first.", title="⚠  Not Configured"), ephemeral=True); return
    role = interaction.guild.get_role(int(rid))
    if role is None:
        await interaction.response.send_message(embed=warn_embed("The configured watchlist role no longer exists. Re-run `/setup`.", title="⚠  Role Missing"), ephemeral=True); return

    await interaction.response.defer()
    try:
        await user.add_roles(role, reason=f"Watchlisted by {interaction.user}: {reason}")
        try: await user.edit(nick="[WATCHLIST]")
        except discord.Forbidden: pass
    except discord.Forbidden:
        await interaction.followup.send(embed=error_embed("I'm missing permissions on that user.", title="✖  Cannot Modify User")); return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(
        title="👁️  WATCHLISTED",
        description=f"User has been placed on the watchlist by {interaction.user.mention}.",
        color=0xFFFFFF,
    )
    embed.add_field(name="Offender", value=user.mention, inline=True)
    embed.add_field(name="Watchlisted by", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=f"Time of watchlist • {now}")
    await interaction.followup.send(embed=embed)


# ---------- /unwatchlist ----------
@bot.tree.command(name="unwatchlist", description="Remove a user from watchlist")
@app_commands.describe(user="User")
async def unwatchlist_cmd(interaction, user: discord.Member):
    if not has_permission(interaction):
        await interaction.response.send_message(embed=error_embed("You don't have permission to use this command."), ephemeral=True); return
    rid = get_guild_cfg(interaction.guild.id).get("watchlist_role")
    if not rid:
        await interaction.response.send_message(embed=warn_embed("Watchlist role isn't configured. Run `/setup` first.", title="⚠  Not Configured"), ephemeral=True); return
    role = interaction.guild.get_role(int(rid))
    if role and role in user.roles:
        try:
            await user.remove_roles(role, reason=f"Unwatchlisted by {interaction.user}")
            try: await user.edit(nick=None)
            except discord.Forbidden: pass
        except discord.Forbidden:
            await interaction.response.send_message(embed=error_embed("I'm missing permissions on that user.", title="✖  Cannot Modify User"), ephemeral=True); return
    await interaction.response.send_message(
        embed=success_embed(f"{user.mention} has been removed from the watchlist.", title="✓  Unwatchlisted"),
        ephemeral=True,
    )
# ---------- /provoked ----------

@bot.tree.command(name="provoked", description="Owner only. Toggle bot lockdown mode.")
async def provoked_cmd(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            embed=error_embed("This command is restricted to the bot owner.", title="✖  Owner Only"),
            ephemeral=True
        )
        return
    cfg = get_guild_cfg(interaction.guild.id)
    current = cfg.get("provoked", False)

    # toggle
    new_state = not current
    set_guild_cfg(interaction.guild.id, "provoked", new_state)

    if new_state:
        embed = warn_embed(
            "Bot is now **LOCKED DOWN**.\n\nAll permission-role users can no longer use commands.",
            title="⚠  Provoked Mode Enabled"
        )
    else:
        embed = success_embed(
            "Bot is back to normal.\n\nPermission-role users can use commands again.",
            title="✓  Provoked Mode Disabled"
        )
    await interaction.response.send_message(embed=embed)
    

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is required.")
    bot.run(TOKEN)
