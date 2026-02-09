import os
import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.environ.get("DISCORD_TOKEN")

# Load relay configuration
with open("relay_config.yml") as f:
    config = yaml.safe_load(f)

AI_CHANNEL_ID = 1429879717284151398   # AI hub channel
RECEIVERS = [int(x) for x in config.get("receivers", [])]
ALLOWED_USERS = [int(x) for x in config.get("allowed_users", [])]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Only allow specific users
    if message.author.id not in ALLOWED_USERS:
        return

    # Forward only if message is in AI channel
    if message.channel.id == AI_CHANNEL_ID:
        for recv_id in RECEIVERS:
            target_channel = bot.get_channel(recv_id)
            if target_channel:
                if message.content:
                    await target_channel.send(message.content)
                for attachment in message.attachments:
                    await target_channel.send(file=await attachment.to_file())

    await bot.process_commands(message)

bot.run(TOKEN)