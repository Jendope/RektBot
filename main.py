import os
import discord
import yaml
from discord.ext import commands
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    print("ERROR: TOKEN environment variable not set.")
    exit(1)

# --- Load relay config ---
with open("relay_config.yml") as f:
    config = yaml.safe_load(f)

# Build SOURCES automatically from pairs (bi-directional)
SOURCES = {}
for a, b in config.get("pairs", []):
    SOURCES.setdefault(int(a), []).append(int(b))
    SOURCES.setdefault(int(b), []).append(int(a))

RECEIVERS = [int(x) for x in config.get("receivers", [])]
ALLOWED_USERS = [int(x) for x in config.get("allowed_users", [])]

# --- Discord bot setup ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Keep-alive server (optional) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Events ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Only relay if author is in ALLOWED_USERS
    if message.author.id not in ALLOWED_USERS:
        return

    # Relay based on SOURCES mapping
    targets = SOURCES.get(message.channel.id, [])
    for target_id in targets:
        target_channel = bot.get_channel(target_id)
        if target_channel:
            if message.content:
                await target_channel.send(message.content)
            for attachment in message.attachments:
                await target_channel.send(file=await attachment.to_file())

    # Always forward to RECEIVERS (Triad + future servers)
    if message.channel.id in SOURCES:  # only relay if source is LN, AI, or TestServer
        for recv_id in RECEIVERS:
            target_channel = bot.get_channel(recv_id)
            if target_channel:
                if message.content:
                    await target_channel.send(message.content)
                for attachment in message.attachments:
                    await target_channel.send(file=await attachment.to_file())

    await bot.process_commands(message)

# --- Run bot ---
keep_alive()
bot.run(TOKEN)