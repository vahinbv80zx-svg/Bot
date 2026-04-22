import os
import json
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN")
CONFIG_FILE = "config.json"
OWNER_ID = 1025704740828491806

VACANT_THUMB = "https://cdn.discordapp.com/attachments/1496355649502580757/1496377629501030400/Black_question_mark.png?ex=69e9a9c4&is=69e85844&hm=c5f1e8c59fb5aff7c11f84e43133b22c7785163c20b0c150b5caf04095e32eb6&"
HEADER_GIF = "https://cdn.discordapp.com/attachments/1496355649502580757/1496377599662755931/WHITE-1.gif?ex=69e9a9bd&is=69e8583d&hm=cae7913688d5a686d7d1da1248509c23b11bacf17387fef4a9d546e6ae9874a7&"

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


# ---------- Leaderboard helpers ----------
def vacant_spot_data():
    return {"vacant": True}


def render_spot_embed(spot_num: int, data: dict, is_first: bool = False) -> discord.Embed:
    if not data or data.get("vacant", True):
        embed = discord.Embed(
            title=f"{spot_num} - Vacant",
            description=(
                "| `Vacant` |\n"
                "<<< | • Information • | >>>\n"
                "Country : Null\n"
                "Stage : Null"
            ),
            color=0x2B2D31,
        )
        embed.set_thumbnail(url=VACANT_THUMB)
    else:
        username = data.get("username", "Unknown")
        discord_un = data.get("discord_username", "")
        roblox_un = data.get("roblox_username", "")
        country = data.get("country", "")
        stage = data.get("stage", "")
        thumb = data.get("thumbnail_url") or VACANT_THUMB
        embed = discord.Embed(
            title=f"{spot_num} - {username}",
            description=(
                f"| `{discord_un}` |\n"
                f"<<< | • {roblox_un} • | >>>\n"
                f"Country : {country}\n"
                f"Stage : {stage}"
            ),
            color=0x2B2D31,
        )
        embed.set_thumbnail(url=thumb)
    if is_first:
        embed.set_image(url=HEADER_GIF)
    return embed


async def refresh_leaderboard(guild: discord.Guild):
    cfg = get_guild_cfg(guild.id)
    lb = cfg.get("leaderboard")
    if not lb:
        return
    channel = guild.get_channel(lb["channel_id"])
    if channel is None:
        return

    start, end = lb["start"], lb["end"]
    spots = lb.get("spots", {})
    spot_nums = list(range(start, end + 1))

    all_embeds = []
    for i, n in enumerate(spot_nums):
        all_embeds.append(render_spot_embed(n, spots.get(str(n)), is_first=(i == 0)))

    chunks = [all_embeds[i:i + 10] for i in range(0, len(all_embeds), 10)]
    message_ids = lb.get("message_ids", [])
    new_message_ids = []

    for idx, chunk in enumerate(chunks):
        if idx < len(message_ids):
            try:
                msg = await channel.fetch_message(message_ids[idx])
                await msg.edit(embeds=chunk)
                new_message_ids.append(msg.id)
                continue
            except discord.NotFound:
                pass
        msg = await channel.send(embeds=chunk)
        new_message_ids.append(msg.id)

    for old_id in message_ids[len(chunks):]:
        try:
            old_msg = await channel.fetch_message(old_id)
            await old_msg.delete()
        except Exception:
            pass

    lb["message_ids"] = new_message_ids
    set_guild_cfg(guild.id, "leaderboard", lb)


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
        title="✨ Moderation & Leaderboard Bot — Help",
        description="A clean moderation companion plus a fully-featured leaderboard manager.",
        color=0x00FFFF,
    )
    embed.add_field(name="🚫  /blacklist", value="Blacklist a user.", inline=False)
    embed.add_field(name="♻️  /unblacklist", value="Restore a blacklisted user.", inline=False)
    embed.add_field(name="👁️  /watchlist", value="Add a user to the watchlist.", inline=False)
    embed.add_field(name="🟢  /unwatchlist", value="Remove a user from the watchlist.", inline=False)
    embed.add_field(name="⚙️  /setup", value="Configure blacklist/watchlist roles.", inline=False)
    embed.add_field(name="🔑  /permission", value="Owner-only. Grant a role bot access.", inline=False)
    embed.add_field(name="🏆  /createlb", value="Create a leaderboard with a range like `1-10`.", inline=False)
    embed.add_field(name="📝  /fillspot", value="Fill in info for a vacant leaderboard spot.", inline=False)
    embed.add_field(name="⬆️  /moveup", value="Move a player up one rank.", inline=False)
    embed.add_field(name="⬇️  /movedown", value="Move a player down one rank.", inline=False)
    embed.add_field(name="❌  /removeplayer", value="Reset a leaderboard spot to vacant.", inline=False)
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
        await interaction.response.send_message("❌ That doesn't look like a valid role ID.", ephemeral=True)
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
                f"⚠️ The blacklist role can still view some channels. Disable channel access first.\n\nVisible: {preview}{more}",
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
        await interaction.response.send_message("❌ You need the **Manage Roles** permission.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("blacklist_role")
    if not role_id:
        await interaction.response.send_message("❌ Blacklist role isn't configured. Run `/setup` first.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message("❌ The configured blacklist role no longer exists.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        original_roles = [r.id for r in user.roles if r != interaction.guild.default_role and r.id != role.id]
        save_user_backup(interaction.guild.id, user.id, "blacklist", {
            "roles": original_roles,
            "nick": user.nick,
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
        await interaction.followup.send("❌ I don't have permission to modify that user.")
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
        await interaction.response.send_message("❌ You need the **Manage Roles** permission.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("blacklist_role")
    if not role_id:
        await interaction.response.send_message("❌ Blacklist role isn't configured.", ephemeral=True)
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
            await user.add_roles(*roles_to_restore, reason=f"Restored by {interaction.user}")
        try:
            await user.edit(nick=saved_nick)
        except discord.Forbidden:
            pass
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to modify that user.")
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
        await interaction.response.send_message("❌ You need the **Manage Roles** permission.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("watchlist_role")
    if not role_id:
        await interaction.response.send_message("❌ Watchlist role isn't configured.", ephemeral=True)
        return

    role = interaction.guild.get_role(int(role_id))
    if role is None:
        await interaction.response.send_message("❌ The configured watchlist role no longer exists.", ephemeral=True)
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
        await interaction.followup.send("❌ I don't have permission to modify that user.")
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
        await interaction.response.send_message("❌ You need the **Manage Roles** permission.", ephemeral=True)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    role_id = cfg.get("watchlist_role")
    if not role_id:
        await interaction.response.send_message("❌ Watchlist role isn't configured.", ephemeral=True)
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
        await interaction.followup.send("❌ I don't have permission to modify that user.")
        return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(title="🟢 UNWATCHLIST", color=0xFFFF00)
    embed.add_field(name="UNWATCHLIST BY", value=interaction.user.mention, inline=False)
    embed.add_field(name="REASON", value=reason, inline=False)
    embed.add_field(name="USER", value=user.mention, inline=False)
    embed.set_footer(text=f"Time of unwatchlist • {now}")
    await interaction.followup.send(embed=embed)


# ---------- /createlb ----------
@bot.tree.command(name="createlb", description="Create a leaderboard with a range like 1-10")
@app_commands.describe(range_input="Range of spots, e.g. 1-10 or 10-20")
async def createlb_cmd(interaction: discord.Interaction, range_input: str):
    if not has_permission(interaction):
        await deny(interaction)
        return

    try:
        parts = [p for p in range_input.replace(" ", "").split("-") if p != ""]
        start = int(parts[0])
        end = int(parts[-1])
        if end < start:
            start, end = end, start
        if end - start + 1 > 50:
            await interaction.response.send_message("❌ Max leaderboard size is 50 spots.", ephemeral=True)
            return
        if start < 1:
            await interaction.response.send_message("❌ Spots must start at 1 or higher.", ephemeral=True)
            return
    except Exception:
        await interaction.response.send_message("❌ Invalid range. Use format like `1-10`.", ephemeral=True)
        return

    spots = {str(n): vacant_spot_data() for n in range(start, end + 1)}
    lb = {
        "channel_id": interaction.channel.id,
        "message_ids": [],
        "start": start,
        "end": end,
        "spots": spots,
    }
    set_guild_cfg(interaction.guild.id, "leaderboard", lb)

    await interaction.response.send_message(f"✅ Leaderboard `{start}-{end}` created.", ephemeral=True)
    await refresh_leaderboard(interaction.guild)


# ---------- /fillspot ----------
@bot.tree.command(name="fillspot", description="Fill information for a vacant spot")
@app_commands.describe(
    spot="Spot number to fill",
    username="Display name (e.g. Ecstscy)",
    discord_username="Discord username",
    roblox_username="Roblox username",
    country="Country (use a flag emoji like 🇺🇸)",
    stage="Stage (e.g. Stage 1 - High)",
    thumbnail_url="Thumbnail URL (Roblox pfp or Discord pfp)",
)
async def fillspot_cmd(
    interaction: discord.Interaction,
    spot: int,
    username: str,
    discord_username: str,
    roblox_username: str,
    country: str,
    stage: str,
    thumbnail_url: str,
):
    if not has_permission(interaction):
        await deny(interaction)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    lb = cfg.get("leaderboard")
    if not lb:
        await interaction.response.send_message("❌ No leaderboard exists. Run `/createlb` first.", ephemeral=True)
        return
    if spot < lb["start"] or spot > lb["end"]:
        await interaction.response.send_message(f"❌ Spot must be between {lb['start']} and {lb['end']}.", ephemeral=True)
        return

    lb.setdefault("spots", {})[str(spot)] = {
        "vacant": False,
        "username": username,
        "discord_username": discord_username,
        "roblox_username": roblox_username,
        "country": country,
        "stage": stage,
        "thumbnail_url": thumbnail_url,
    }
    set_guild_cfg(interaction.guild.id, "leaderboard", lb)

    await interaction.response.send_message(f"✅ Spot {spot} updated.", ephemeral=True)
    await refresh_leaderboard(interaction.guild)


# ---------- /moveup ----------
@bot.tree.command(name="moveup", description="Move a player up one rank (lower number)")
@app_commands.describe(spot="Current spot number of the player to move up")
async def moveup_cmd(interaction: discord.Interaction, spot: int):
    if not has_permission(interaction):
        await deny(interaction)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    lb = cfg.get("leaderboard")
    if not lb:
        await interaction.response.send_message("❌ No leaderboard exists.", ephemeral=True)
        return
    if spot <= lb["start"] or spot > lb["end"]:
        await interaction.response.send_message(f"❌ Cannot move spot {spot} up.", ephemeral=True)
        return

    spots = lb.setdefault("spots", {})
    a, b = str(spot), str(spot - 1)
    spots[a], spots[b] = spots.get(b, vacant_spot_data()), spots.get(a, vacant_spot_data())
    set_guild_cfg(interaction.guild.id, "leaderboard", lb)

    await interaction.response.send_message(f"✅ Moved spot {spot} → {spot - 1}.", ephemeral=True)
    await refresh_leaderboard(interaction.guild)


# ---------- /movedown ----------
@bot.tree.command(name="movedown", description="Move a player down one rank (higher number)")
@app_commands.describe(spot="Current spot number of the player to move down")
async def movedown_cmd(interaction: discord.Interaction, spot: int):
    if not has_permission(interaction):
        await deny(interaction)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    lb = cfg.get("leaderboard")
    if not lb:
        await interaction.response.send_message("❌ No leaderboard exists.", ephemeral=True)
        return
    if spot < lb["start"] or spot >= lb["end"]:
        await interaction.response.send_message(f"❌ Cannot move spot {spot} down.", ephemeral=True)
        return

    spots = lb.setdefault("spots", {})
    a, b = str(spot), str(spot + 1)
    spots[a], spots[b] = spots.get(b, vacant_spot_data()), spots.get(a, vacant_spot_data())
    set_guild_cfg(interaction.guild.id, "leaderboard", lb)

    await interaction.response.send_message(f"✅ Moved spot {spot} → {spot + 1}.", ephemeral=True)
    await refresh_leaderboard(interaction.guild)


# ---------- /removeplayer ----------
@bot.tree.command(name="removeplayer", description="Remove a player and reset their spot to vacant")
@app_commands.describe(spot="Spot number to clear")
async def removeplayer_cmd(interaction: discord.Interaction, spot: int):
    if not has_permission(interaction):
        await deny(interaction)
        return

    cfg = get_guild_cfg(interaction.guild.id)
    lb = cfg.get("leaderboard")
    if not lb:
        await interaction.response.send_message("❌ No leaderboard exists.", ephemeral=True)
        return
    if spot < lb["start"] or spot > lb["end"]:
        await interaction.response.send_message(f"❌ Spot must be between {lb['start']} and {lb['end']}.", ephemeral=True)
        return

    lb.setdefault("spots", {})[str(spot)] = vacant_spot_data()
    set_guild_cfg(interaction.guild.id, "leaderboard", lb)

    await interaction.response.send_message(f"✅ Spot {spot} reset to vacant.", ephemeral=True)
    await refresh_leaderboard(interaction.guild)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN environment variable is required.")
    bot.run(TOKEN)
