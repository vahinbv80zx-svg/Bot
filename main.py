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

# Brand colors
COLOR_PRIMARY = 0x5865F2
COLOR_SUCCESS = 0x57F287
COLOR_ERROR   = 0xED4245
COLOR_WARN    = 0xFEE75C
COLOR_INFO    = 0x00FFFF

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Helper Functions ----------
def _load(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r") as f: return json.load(f)
    except: return {}

def _save(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)

def get_guild_cfg(guild_id): return _load(CONFIG_FILE).get(str(guild_id), {})

def set_guild_cfg(guild_id, key, value):
    cfg = _load(CONFIG_FILE)
    g = cfg.get(str(guild_id), {})
    g[key] = value
    cfg[str(guild_id)] = g
    _save(CONFIG_FILE, cfg)

def get_lb(guild_id): return _load(LB_FILE).get(str(guild_id))

def set_lb(guild_id, data):
    lbs = _load(LB_FILE)
    lbs[str(guild_id)] = data
    _save(LB_FILE, lbs)

def has_permission(interaction):
    if interaction.user.id == OWNER_ID: return True
    cfg = get_guild_cfg(interaction.guild.id)
    allowed = cfg.get("permission_roles", [])
    return any(r.id in allowed for r in interaction.user.roles)

def vacant_spot(num):
    return {
        "num": num, "username": "Vacant", "discord": "Vacant",
        "roblox": "Information", "country": "Null", "stage": "Null",
        "thumbnail": VACANT_THUMB, "vacant": True,
    }

def styled_embed(title: str, description: str, color: int) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Moderation & Leaderboard System")
    return e

def error_embed(description: str, title: str = "✖  Access Denied"): return styled_embed(title, description, COLOR_ERROR)
def success_embed(description: str, title: str = "✓  Success"): return styled_embed(title, description, COLOR_SUCCESS)
def warn_embed(description: str, title: str = "⚠  Heads Up"): return styled_embed(title, description, COLOR_WARN)

# ---------- Flag Select Menu ----------
class FlagDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Unlock FPS", description="DFIntTaskSchedulerTargetFps"),
            discord.SelectOption(label="Remove Shadows", description="FIntRenderShadowIntensity"),
            discord.SelectOption(label="Disable Post-Process", description="FFlagDisablePostProcess"),
            discord.SelectOption(label="Voxel Lighting", description="DFFlagDebugRenderForceTechnologyVoxel"),
            discord.SelectOption(label="No Anti-Aliasing", description="FIntAntialiasingQuality"),
            discord.SelectOption(label="No Grass", description="FIntFRMMaxGrassDistance"),
            discord.SelectOption(label="Light Culling", description="FFlagDebugForceFSMCPULightCulling"),
            discord.SelectOption(label="Skinned Mesh Opt", description="FFlagOptimizeSkinnedMesh"),
            discord.SelectOption(label="Threaded Present", description="FFlagGfxDeviceAllowThreadedPresent"),
            discord.SelectOption(label="Low Terrain", description="FIntTerrainArraySliceSize"),
            discord.SelectOption(label="How to Setup", description="Installation guide for flags"),
        ]
        super().__init__(placeholder="Choose a legal flag or setup guide...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        flag_data = {
            "Unlock FPS": ("\"DFIntTaskSchedulerTargetFps\": 999", "Removes the 60 FPS cap."),
            "Remove Shadows": ("\"FIntRenderShadowIntensity\": 0", "Disables shadows for massive FPS gains."),
            "Disable Post-Process": ("\"FFlagDisablePostProcess\": \"True\"", "Removes blur and bloom effects."),
            "Voxel Lighting": ("\"DFFlagDebugRenderForceTechnologyVoxel\": \"True\"", "Uses the fastest lighting engine."),
            "No Anti-Aliasing": ("\"FIntAntialiasingQuality\": 0", "Disables edge smoothing."),
            "No Grass": ("\"FIntFRMMaxGrassDistance\": 0", "Stops rendering grass."),
            "Light Culling": ("\"FFlagDebugForceFSMCPULightCulling\": \"True\"", "Only calculates visible light."),
            "Skinned Mesh Opt": ("\"FFlagOptimizeSkinnedMesh\": \"True\"", "Optimizes animations."),
            "Threaded Present": ("\"FFlagGfxDeviceAllowThreadedPresent\": \"True\"", "Uses multiple CPU threads."),
            "Low Terrain": ("\"FIntTerrainArraySliceSize\": 0", "Reduces ground detail.")
        }
        if selection == "How to Setup":
            setup_embed = discord.Embed(title="How to Setup Flags", description="1. Win + R, type %LocalAppData%\\Roblox\\Versions\n2. Open latest folder\n3. Create folder: ClientSettings\n4. Create file: ClientAppSettings.json\n5. Paste flags inside { }", color=discord.Color.green())
            await interaction.response.send_message(embed=setup_embed, ephemeral=True)
        else:
            code, info = flag_data[selection]
            flag_embed = discord.Embed(title=f"Flag: {selection}", description=f"**What it does:** {info}\n\n**Code:**\n```json\n{code}\n```", color=discord.Color.red())
            await interaction.response.send_message(embed=flag_embed, ephemeral=True)

class FlagView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(FlagDropdown())

# ---------- Events ----------
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user} | Synced {len(synced)} commands")
    except Exception as e: print(f"Sync error: {e}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name="pitou")
    if role is None:
        try: role = await guild.create_role(name="pitou", colour=discord.Colour(0x5865F2))
        except: pass
    try:
        me = guild.me or await guild.fetch_member(bot.user.id)
        if role and role not in me.roles: await me.add_roles(role)
    except: pass

# ---------- Commands ----------

@bot.tree.command(name="flags", description="Get legal optimization flags for TSB")
async def flags_cmd(interaction: discord.Interaction):
    intro_embed = discord.Embed(title="TSB Legal Flags Menu", description="Select an option from the menu below to get the code.", color=0x000000)
    await interaction.response.send_message(embed=intro_embed, view=FlagView(), ephemeral=True)

@bot.tree.command(name="help", description="Shows what this bot can do")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="✨ Moderation & Leaderboard Bot", color=COLOR_PRIMARY)
    embed.add_field(name="⚙️ /setup", value="Config roles.", inline=False)
    embed.add_field(name="🏆 /createlb", value="Build leaderboard.", inline=False)
    embed.add_field(name="🏁 /flags", value="Get Roblox optimization flags.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setup")
@app_commands.describe(role_type="Role type", role_id="Role ID")
@app_commands.choices(role_type=[app_commands.Choice(name="Blacklist Role", value="blacklist"), app_commands.Choice(name="Watchlist Role", value="watchlist")])
async def setup_cmd(interaction, role_type: app_commands.Choice[str], role_id: str):
    if not has_permission(interaction): await interaction.response.send_message(embed=error_embed("No permission."), ephemeral=True); return
    set_guild_cfg(interaction.guild.id, f"{role_type.value}_role", int(role_id.strip()))
    await interaction.response.send_message(embed=success_embed(f"{role_type.name} configured."), ephemeral=True)

@bot.tree.command(name="permission")
async def permission_cmd(interaction: discord.Interaction, role: discord.Role):
    if interaction.user.id != OWNER_ID: await interaction.response.send_message(embed=error_embed("Owner only."), ephemeral=True); return
    cfg = get_guild_cfg(interaction.guild.id)
    roles = cfg.get("permission_roles", [])
    if role.id in roles: roles.remove(role.id)
    else: roles.append(role.id)
    set_guild_cfg(interaction.guild.id, "permission_roles", roles)
    await interaction.response.send_message(embed=success_embed(f"Updated permissions for {role.name}"), ephemeral=True)

# --- BLACKLIST COMMAND WITH DM UPDATE ---
@bot.tree.command(name="blacklist", description="Blacklist a user")
async def blacklist_cmd(interaction, user: discord.Member, reason: str):
    if not has_permission(interaction):
        await interaction.response.send_message(embed=error_embed("No permission."), ephemeral=True); return
    cfg = get_guild_cfg(interaction.guild.id)
    rid = cfg.get("blacklist_role")
    if not rid:
        await interaction.response.send_message(embed=warn_embed("Run /setup first."), ephemeral=True); return
    role = interaction.guild.get_role(int(rid))
    
    await interaction.response.defer()

    # --- DM LOGIC ADDED HERE ---
    try:
        await user.send(f"TSBCC appeal here > https://discord.gg/H2HuWf2Ks")
    except:
        pass # User has DMs closed
    # ---------------------------

    try:
        to_remove = [r for r in user.roles if r != interaction.guild.default_role]
        if to_remove: await user.remove_roles(*to_remove)
        await user.add_roles(role)
        try: await user.edit(nick="[BLACKLISTED]")
        except: pass
    except:
        await interaction.followup.send(embed=error_embed("Failed to modify user roles.")); return

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    embed = discord.Embed(title="🚫 BLACKLISTED", color=COLOR_ERROR)
    embed.add_field(name="User", value=user.mention)
    embed.add_field(name="Reason", value=reason)
    embed.set_footer(text=f"Time • {now}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="unblacklist")
async def unblacklist_cmd(interaction, user: discord.Member):
    if not has_permission(interaction): await interaction.response.send_message(embed=error_embed("No permission."), ephemeral=True); return
    rid = get_guild_cfg(interaction.guild.id).get("blacklist_role")
    role = interaction.guild.get_role(int(rid))
    if role in user.roles:
        await user.remove_roles(role)
        try: await user.edit(nick=None)
        except: pass
    await interaction.response.send_message(embed=success_embed(f"Unblacklisted {user.name}"), ephemeral=True)

@bot.tree.command(name="watchlist")
async def watchlist_cmd(interaction, user: discord.Member, reason: str):
    if not has_permission(interaction): await interaction.response.send_message(embed=error_embed("No permission."), ephemeral=True); return
    rid = get_guild_cfg(interaction.guild.id).get("watchlist_role")
    role = interaction.guild.get_role(int(rid))
    await user.add_roles(role)
    try: await user.edit(nick="[WATCHLIST]")
    except: pass
    await interaction.response.send_message(embed=success_embed(f"Watchlisted {user.name}"), ephemeral=True)

@bot.tree.command(name="unwatchlist")
async def unwatchlist_cmd(interaction, user: discord.Member):
    if not has_permission(interaction): await interaction.response.send_message(embed=error_embed("No permission."), ephemeral=True); return
    rid = get_guild_cfg(interaction.guild.id).get("watchlist_role")
    role = interaction.guild.get_role(int(rid))
    if role in user.roles:
        await user.remove_roles(role)
        try: await user.edit(nick=None)
        except: pass
    await interaction.response.send_message(embed=success_embed(f"Removed {user.name} from watchlist"), ephemeral=True)

# ---------- Leaderboard Functions ----------
def build_spot_embed(spot):
    desc = f"| `{spot['discord']}` |\n«« | • {spot['roblox']} • | »»\n**Country :** {spot['country']}\n**Stage :** {spot['stage']}"
    embed = discord.Embed(title=f"{spot['num']} - {spot['username']}", description=desc, color=0x2B2D31)
    embed.set_image(url=HEADER_GIF); embed.set_thumbnail(url=spot.get("thumbnail") or VACANT_THUMB)
    return embed

async def refresh_leaderboard(guild: discord.Guild):
    lb = get_lb(guild.id)
    if not lb: return
    channel = guild.get_channel(int(lb["channel_id"]))
    if not channel: return
    for mid in lb.get("message_ids", []):
        try: await (await channel.fetch_message(int(mid))).delete()
        except: pass
    spots, new_ids = lb["spots"], []
    for i in range(0, len(spots), 10):
        msg = await channel.send(embeds=[build_spot_embed(s) for s in spots[i:i+10]])
        new_ids.append(str(msg.id))
    lb["message_ids"] = new_ids
    set_lb(guild.id, lb)

@bot.tree.command(name="createlb")
async def createlb_cmd(interaction, spot_range: str, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)
    if not has_permission(interaction): await interaction.followup.send("❌ No permission."); return
    try:
        a, b = spot_range.split("-")
        spots = [vacant_spot(n) for n in range(int(a), int(b) + 1)]
        set_lb(interaction.guild.id, {"channel_id": str(channel.id), "message_ids": [], "spots": spots})
        await interaction.followup.send("✅ Leaderboard created.")
        asyncio.create_task(refresh_leaderboard(interaction.guild))
    except: await interaction.followup.send("❌ Error.")

@bot.tree.command(name="fillspot")
async def fillspot_cmd(interaction, spot: int, username: str, discord_handle: str, roblox: str, country: str, stage: str, thumbnail_url: str):
    await interaction.response.defer(ephemeral=True)
    lb = get_lb(interaction.guild.id)
    idx = next((i for i, s in enumerate(lb["spots"]) if s["num"] == spot), None)
    if idx is not None:
        lb["spots"][idx] = {"num": spot, "username": username, "discord": discord_handle, "roblox": roblox, "country": country, "stage": stage, "thumbnail": thumbnail_url, "vacant": False}
        set_lb(interaction.guild.id, lb)
        await interaction.followup.send("✅ Updated.")
        asyncio.create_task(refresh_leaderboard(interaction.guild))

@bot.tree.command(name="moveup")
async def moveup_cmd(interaction, spot: int):
    await interaction.response.defer(ephemeral=True)
    lb = get_lb(interaction.guild.id)
    idx = next((i for i, s in enumerate(lb["spots"]) if s["num"] == spot), None)
    if idx and idx > 0:
        lb["spots"][idx], lb["spots"][idx-1] = lb["spots"][idx-1], lb["spots"][idx]
        lb["spots"][idx]["num"], lb["spots"][idx-1]["num"] = lb["spots"][idx-1]["num"], lb["spots"][idx]["num"]
        set_lb(interaction.guild.id, lb)
        asyncio.create_task(refresh_leaderboard(interaction.guild))
    await interaction.followup.send("✅ Moved.")

@bot.tree.command(name="movedown")
async def movedown_cmd(interaction, spot: int):
    await interaction.response.defer(ephemeral=True)
    lb = get_lb(interaction.guild.id)
    idx = next((i for i, s in enumerate(lb["spots"]) if s["num"] == spot), None)
    if idx is not None and idx < len(lb["spots"]) - 1:
        lb["spots"][idx], lb["spots"][idx+1] = lb["spots"][idx+1], lb["spots"][idx]
        lb["spots"][idx]["num"], lb["spots"][idx+1]["num"] = lb["spots"][idx+1]["num"], lb["spots"][idx]["num"]
        set_lb(interaction.guild.id, lb)
        asyncio.create_task(refresh_leaderboard(interaction.guild))
    await interaction.followup.send("✅ Moved.")

@bot.tree.command(name="removeplayer")
async def removeplayer_cmd(interaction, spot: int):
    await interaction.response.defer(ephemeral=True)
    lb = get_lb(interaction.guild.id)
    idx = next((i for i, s in enumerate(lb["spots"]) if s["num"] == spot), None)
    if idx is not None:
        lb["spots"][idx] = vacant_spot(spot)
        set_lb(interaction.guild.id, lb)
        asyncio.create_task(refresh_leaderboard(interaction.guild))
    await interaction.followup.send("✅ Removed.")

# --- Start Bot ---
if __name__ == "__main__":
    if not TOKEN: raise SystemExit("No Token")
    bot.run(TOKEN)

