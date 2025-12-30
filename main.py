# Discord Bot API Fetcher for FiveM Cheating Servers
# Made by Kowy
# Visit https://github.com/kqwyy

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import time

API_KEY = "APIKEY_HERE"
BOT_TOKEN = "TOKEN_HERE"
BASE_URL = "APIURL_HERE"
ALLOWED_ROLES = [ROLEIDS_HERE]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# Helper Funktionen

async def fetch_data(endpoint: str, param: str = ""):
    url = f"{BASE_URL}/{endpoint}/{param}" if endpoint else f"{BASE_URL}/{param}"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[ERROR] Fetch failed: {url} (Status {resp.status})")
            return {}

async def fetch_identifier(identifier: str):
    url = f"{BASE_URL}/identifier/{identifier}"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[ERROR] Identifier fetch failed: {identifier} (Status {resp.status})")
            return {}

async def fetch_all_identifiers(raw_ids: list):
    identifiers_data = {
        "discord": [],
        "steam": [],
        "license": [],
        "license2": [],
        "live": []
    }
    # parallele Abfragen für schnellere Verarbeitung
    tasks_list = []
    for raw_id in raw_ids:
        identifier = raw_id if ":" in raw_id else f"discord:{raw_id}"
        tasks_list.append(fetch_identifier(identifier))
    results = await asyncio.gather(*tasks_list)
    for id_data in results:
        for key in identifiers_data.keys():
            if key in id_data and id_data[key]:
                identifiers_data[key].extend(id_data[key])
    return identifiers_data


# Rollencheck Decorator

def is_allowed_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        roles_ids = [role.id for role in member.roles]
        if not any(r in roles_ids for r in ALLOWED_ROLES):
            await interaction.response.send_message(
                "❌ You do not have the permission to use this command.", ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)


# Server Paginator

class ServerPaginator(discord.ui.View):
    def __init__(self, servers: list):
        super().__init__(timeout=None)
        self.servers = servers
        self.current_page = 0
        self.max_per_page = 10
        self.max_page = (len(servers) - 1) // self.max_per_page
        self.message = None

        self.prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.red)
        self.page_btn = discord.ui.Button(label=f"Page {self.current_page+1}/{self.max_page+1}", style=discord.ButtonStyle.gray, disabled=True)
        self.next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.red)

        self.add_item(self.prev_btn)
        self.add_item(self.page_btn)
        self.add_item(self.next_btn)

        self.prev_btn.callback = self.prev_page
        self.next_btn.callback = self.next_page

    async def get_embed(self):
        start = self.current_page * self.max_per_page
        end = start + self.max_per_page
        embed = discord.Embed(title="🛡️ Blacklisted Discords", color=discord.Color.red())
        embed.set_image(url="IMAGE_HERE")
        for server in self.servers[start:end]:
            name = server.get("name", "Unknown")
            ts = int(server.get("time", 0)/1000) if server.get("time") else 0
            roles = server.get("roles", [])
            roles_str = "\n".join([f"- {r.get('name','?')}" for r in roles]) if roles else "No role"
            embed.add_field(name=f"**{name}** - <t:{ts}:R>", value=roles_str, inline=False)
        return embed

    async def send_embed(self, interaction: discord.Interaction):
        embed = await self.get_embed()
        self.page_btn.label = f"Page {self.current_page+1}/{self.max_page+1}"
        if self.message is None:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
            self.message = await interaction.original_response()
        else:
            await self.message.edit(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        self.current_page = max(self.current_page - 1, 0)
        await self.send_embed(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page = min(self.current_page + 1, self.max_page)
        await self.send_embed(interaction)


# Check Buttons View

class CheckButtons(discord.ui.View):
    def __init__(self, user_id: str, messages_count: int, identifiers_data: dict, servers_list: list, cheats_count: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.servers_list = servers_list
        self.identifiers_data = identifiers_data

        self.add_item(discord.ui.Button(label=f"📨 Messages: {messages_count}", style=discord.ButtonStyle.red))
        self.add_item(discord.ui.Button(label=f"🆔 Identifiers: {sum(len(v) for v in identifiers_data.values())}", style=discord.ButtonStyle.red))
        self.add_item(discord.ui.Button(label=f"🛡️ Servers: {len(servers_list)}", style=discord.ButtonStyle.red))
        self.add_item(discord.ui.Button(label=f"⚠️ Cheats: {cheats_count}", style=discord.ButtonStyle.red))

        self.children[0].callback = self.messages_callback
        self.children[1].callback = self.identifiers_callback
        self.children[2].callback = self.servers_callback
        self.children[3].callback = self.cheats_callback

    async def messages_callback(self, interaction: discord.Interaction):
        data = await fetch_data("messages", self.user_id)
        messages_url = data.get("url", None)
        embed = discord.Embed(title="📨 Messages", color=discord.Color.red())
        embed.set_image(url="IMAGE_HERE")
        embed.description = f"[See all messages]({messages_url})" if messages_url else "No messages found."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def identifiers_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🆔 Identifiers", color=discord.Color.red())
        embed.set_image(url="IMAGE_HERE")
        if any(self.identifiers_data.values()):
            for key, values in self.identifiers_data.items():
                if values:
                    embed.add_field(name=f"{key.capitalize()} IDs", value="\n".join(values), inline=False)
        else:
            embed.description = "No identifiers found."
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def servers_callback(self, interaction: discord.Interaction):
        paginator = ServerPaginator(self.servers_list)
        await paginator.send_embed(interaction)

    async def cheats_callback(self, interaction: discord.Interaction):
        data = await fetch_data("cheat_customer", self.user_id)
        found = data.get("found", [])
        embed = discord.Embed(title="⚠️ Cheater Check", color=discord.Color.red())
        embed.set_image(url="IMAGE_HERE")
        if not found:
            embed.description = "No cheats found ✅"
        else:
            embed.description = "Cheats found ❌"
            embed.add_field(name="Cheats found", value="\n".join(found), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# Slash Command

@bot.tree.command(name="check", description="Check an user")
@is_allowed_role()
async def check_slash(interaction: discord.Interaction, user_id: str):
    # sofort eine Antwort senden, um Interaction timeout zu verhindern
    await interaction.response.send_message("⏳ User is checked...", ephemeral=True)

    # Discord User abrufen
    try:
        user = await bot.fetch_user(int(user_id))
        account_created = user.created_at.strftime("%d.%m.%Y %H:%M:%S")
    except Exception as e:
        print(f"[ERROR] Could not get user data: {e}")
        account_created = "Unknown"

    # Basisdaten
    data_messages = await fetch_data("messages", user_id)
    data_user = await fetch_data("", user_id)
    data_cheats = await fetch_data("cheat_customer", user_id)

    messages_count = len(data_messages.get("messages", []))
    cheats_count = len(data_cheats.get("found", []))
    servers_list = data_user.get("info", [])

    # Identifier
    raw_ids = data_user.get("raw_identifiers", [])
    if not raw_ids:
        raw_ids = [f"discord:{user_id}"]

    identifiers_data = await fetch_all_identifiers(raw_ids)
    print(f"[DEBUG] Alle Identifier gesammelt für {user_id}: {identifiers_data}")

    ts_now = int(time.time())
    embed = discord.Embed(title="▶ User Check Completed", color=discord.Color.red())
    embed.add_field(
        name="🔍 User Information",
        value=f"• **User ID:** {user_id}\n• **Ping:** <@{user_id}>\n• **Account Created:** {account_created}",
        inline=False
    )
    embed.add_field(
        name="🚨 Status Overview",
        value=f"• Servers found: {len(servers_list)}\n• Messages found: {messages_count}\n• Marked as Cheater?: {'⚠️ Yes' if cheats_count else '✅ No'}",
        inline=False
    )
    embed.add_field(
        name="📅 Check Details",
        value=f"• Requested by: {interaction.user.mention}\n• Time: <t:{ts_now}:R>",
        inline=False
    )
    embed.set_image(url="IMAGE_HERE")

    view = CheckButtons(user_id, messages_count, identifiers_data, servers_list, cheats_count)
    # followup senden, nachdem die abfragen abgeschlossen sind
    await interaction.followup.send(embed=embed, view=view, ephemeral=False)


# === NEW: Masscheck Command (Modal) ===

class MultiCheckModal(discord.ui.Modal, title="Masscheck - Paste Discord IDs (one per line)"):
    ids = discord.ui.TextInput(label="Discord IDs", style=discord.TextStyle.paragraph, placeholder="123456789012345678\n234567890123456789", required=True, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.ids.value.strip()
        # split by newline and remove empty lines
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        # limit to 30 ids to avoid abuse/timeout
        if not lines:
            await interaction.response.send_message("No IDs provided.", ephemeral=True)
            return
        if len(lines) > 30:
            await interaction.response.send_message("Please provide at most 30 IDs at once.", ephemeral=True)
            return

        await interaction.response.defer()  # defer while we process

        async def process_user(uid: str):
            # try to get basic discord user info (non-blocking failures)
            try:
                usr = await bot.fetch_user(int(uid))
                created = usr.created_at.strftime("%d.%m.%Y %H:%M:%S")
            except Exception:
                created = "Unknown"

            data_messages = await fetch_data("messages", uid)
            data_user = await fetch_data("", uid)
            data_cheats = await fetch_data("cheat_customer", uid)

            messages_count = len(data_messages.get("messages", []))
            cheats_count = len(data_cheats.get("found", []))
            servers_list = data_user.get("info", [])

            raw_ids = data_user.get("raw_identifiers", [])
            if not raw_ids:
                raw_ids = [f"discord:{uid}"]

            identifiers_data = await fetch_all_identifiers(raw_ids)

            summary = {
                "id": uid,
                "created": created,
                "messages_count": messages_count,
                "cheats_count": cheats_count,
                "servers_count": len(servers_list),
                "identifiers_count": sum(len(v) for v in identifiers_data.values())
            }
            return summary

        # process all users concurrently
        tasks = [process_user(u) for u in lines]
        results = await asyncio.gather(*tasks)

        # Build embeds (max 10 summaries per embed to avoid hitting field limits)
        embeds = []
        chunk_size = 10
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i+chunk_size]
            emb = discord.Embed(title=f"Masscheck Results ({i+1}-{i+len(chunk)})", color=discord.Color.red())
            emb.set_image(url="IMAGE_HERE")
            for r in chunk:
                cheat_flag = '⚠️ Yes' if r['cheats_count'] else '✅ No'
                emb.add_field(name=f"User ID: {r['id']}", value=(f"• Ping: <@{r['id']}>\n"
                                                         f"• Account Created: {r['created']}\n"
                                                         f"• Servers: {r['servers_count']}\n"
                                                         f"• Messages: {r['messages_count']}\n"
                                                         f"• Identifiers: {r['identifiers_count']}\n"
                                                         f"• Marked as Cheater?: {cheat_flag}"), inline=False)
            embeds.append(emb)

        # send all embeds as followups
        for emb in embeds:
            await interaction.followup.send(embed=emb, ephemeral=False)


@bot.tree.command(name="masscheck", description="Check multiple discord users at once")
@is_allowed_role()
async def masscheck_slash(interaction: discord.Interaction):
    modal = MultiCheckModal()
    await interaction.response.send_modal(modal)


# Ping Activity

@tasks.loop(seconds=60)
async def update_activity():
    if bot.is_ready():
        latency_ms = round(bot.latency * 1000)
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"Bot Ping: {latency_ms}ms"))

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash Commands synchronisiert.")
    except Exception as e:
        print(e)
    update_activity.start()

bot.run(BOT_TOKEN)

