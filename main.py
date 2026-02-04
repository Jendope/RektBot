import os
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

# --- Token from Replit Secrets ---
TOKEN = os.environ["TOKEN"]

# --- IDs ---
ROLE_ID = 1414914863498788875
SOURCE_CHANNEL_ID = 1456173014931603456
TARGET_CHANNEL_ID = 1429879717284151398

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

@bot.command()
async def kickrekt(ctx):
    role = ctx.guild.get_role(ROLE_ID)
    if not role:
        await ctx.send("Role not found.")
        return

    kicked = 0
    for member in role.members:
        try:
            await member.kick(reason="Has Rekt Citizen role")
            kicked += 1
        except Exception as e:
            print(f"Failed to kick {member}: {e}")

    await ctx.send(f"Kicked {kicked} members with role Rekt Citizen.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Relay from source → target
    if message.channel.id == SOURCE_CHANNEL_ID:
        target_channel = bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel:
            if message.content:
                await target_channel.send(f"{message.author}: {message.content}")
            for attachment in message.attachments:
                await target_channel.send(file=await attachment.to_file())

    # Allow commands to work
    await bot.process_commands(message)

# --- Run bot ---
keep_alive()
bot.run(TOKEN)