import os
import discord
from discord.ext import commands
import asyncio
from flask import Flask
from threading import Thread

# --- Token from Replit Secrets ---
TOKEN = os.environ["TOKEN"]

# --- IDs ---
ROLE_ID = 1414914863498788875  # Rekt Citizen role ID
CHANNEL_1_ID = 1456173014931603456  # Server 1 channel
CHANNEL_2_ID = 1429879717284151398  # Server 2 channel

# --- Intents ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Keep-alive server for Replit ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Events & Commands ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Kick command with confirmation + rate-limit handling
@bot.command()
async def kickrekt(ctx):
    await ctx.send("⚠️ Are you sure you want to mass‑kick all members with the Rekt Citizen role? Type `yes` to confirm.")

    def check(m):
        return m.author == ctx.author and m.content.lower() == "yes"

    try:
        await bot.wait_for("message", check=check, timeout=30.0)
        role = ctx.guild.get_role(ROLE_ID)
        if not role:
            await ctx.send("Role not found.")
            return

        kicked = 0
        for member in role.members:
            try:
                await member.kick(reason="Has Rekt Citizen role")
                kicked += 1
                await asyncio.sleep(1)  # delay to avoid rate limits
            except Exception as e:
                print(f"Failed to kick {member}: {e}")

        await ctx.send(f"Kicked {kicked} members with role Rekt Citizen.")
    except asyncio.TimeoutError:
        await ctx.send("Kick cancelled (no confirmation received).")

# Relay messages + attachments bi-directionally
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Relay Channel 1 → Channel 2
    if message.channel.id == CHANNEL_1_ID:
        target_channel = bot.get_channel(CHANNEL_2_ID)
        if target_channel:
            if message.content:
                await target_channel.send(f"[Server1] {message.author}: {message.content}")
            for attachment in message.attachments:
                await target_channel.send(file=await attachment.to_file())

    # Relay Channel 2 → Channel 1
    elif message.channel.id == CHANNEL_2_ID:
        target_channel = bot.get_channel(CHANNEL_1_ID)
        if target_channel:
            if message.content:
                await target_channel.send(f"[Server2] {message.author}: {message.content}")
            for attachment in message.attachments:
                await target_channel.send(file=await attachment.to_file())

    # Keep commands working
    await bot.process_commands(message)

# --- Run bot ---
keep_alive()
bot.run(TOKEN)