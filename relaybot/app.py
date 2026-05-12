import os
import io
import logging
from typing import Optional

import discord
import yaml
from discord.ext import commands
from dotenv import load_dotenv


# Load .env for local development
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_PATH = os.getenv("CONFIG_PATH", "relay_config.yml")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("rektbot-relay")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def to_int_set(values) -> set[int]:
    return {int(x) for x in values or []}


config = load_config()

SOURCE_CHANNELS = to_int_set(config.get("source_channels"))
RECEIVERS = to_int_set(config.get("receivers"))

ALLOWED_SENDERS = to_int_set(config.get("allowed_senders"))

# Keep support for old config name, just in case
ALLOWED_SENDERS |= to_int_set(config.get("allowed_users"))

ADD_HEADER = bool(config.get("add_header", True))
COPY_EMBEDS = bool(config.get("copy_embeds", True))
DISABLE_MENTIONS = bool(config.get("disable_mentions", True))

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN. Put it in .env locally or in Render/Railway environment variables.")

if not SOURCE_CHANNELS:
    raise RuntimeError("No source_channels found in relay_config.yml.")

if not RECEIVERS:
    raise RuntimeError("No receivers found in relay_config.yml.")

if not ALLOWED_SENDERS:
    log.warning("No allowed_senders configured. No messages will be relayed.")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def split_message(text: str, limit: int = 1900) -> list[str]:
    """
    Discord has a 2000-character message limit.
    We use 1900 to leave space for headers.
    """
    if not text:
        return []

    chunks = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
                current = ""

            while len(line) > limit:
                chunks.append(line[:limit])
                line = line[limit:]

        current += line

    if current:
        chunks.append(current)

    return chunks


def build_header(message: discord.Message) -> str:
    guild_name = message.guild.name if message.guild else "Unknown Server"
    channel_name = getattr(message.channel, "name", str(message.channel.id))
    author_name = str(message.author)

    return f"**Forwarded from `{guild_name}` / `#{channel_name}` by `{author_name}`**"


def is_allowed_sender(message: discord.Message) -> bool:
    return message.author.id in ALLOWED_SENDERS


async def get_target_channel(channel_id: int) -> Optional[discord.abc.Messageable]:
    channel = bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.Forbidden:
            log.error("No permission to access target channel: %s", channel_id)
            return None
        except discord.NotFound:
            log.error("Target channel not found: %s", channel_id)
            return None
        except discord.HTTPException as e:
            log.error("Failed to fetch target channel %s: %s", channel_id, e)
            return None

    if not hasattr(channel, "send"):
        log.error("Target is not a sendable channel: %s", channel_id)
        return None

    return channel


async def attachment_to_file(attachment: discord.Attachment) -> discord.File:
    data = await attachment.read()

    return discord.File(
        fp=io.BytesIO(data),
        filename=attachment.filename,
        description=attachment.description,
    )


async def forward_message(message: discord.Message, target_channel: discord.abc.Messageable):
    allowed_mentions = (
        discord.AllowedMentions.none()
        if DISABLE_MENTIONS
        else discord.AllowedMentions.all()
    )

    header = build_header(message) if ADD_HEADER else ""
    content = message.content.strip() if message.content else ""
    chunks = split_message(content)

    embeds = []
    if COPY_EMBEDS and message.embeds:
        embeds = [embed.copy() for embed in message.embeds[:10]]

    # Case 1: text message, possibly with embeds
    if chunks:
        first_content = f"{header}\n{chunks[0]}" if header else chunks[0]

        await target_channel.send(
            content=first_content[:2000],
            embeds=embeds,
            allowed_mentions=allowed_mentions,
        )

        for chunk in chunks[1:]:
            await target_channel.send(
                content=chunk[:2000],
                allowed_mentions=allowed_mentions,
            )

    # Case 2: embed-only message
    elif embeds:
        await target_channel.send(
            content=header or None,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
        )

    # Case 3: attachment-only message
    elif header and not message.attachments:
        await target_channel.send(
            content=header,
            allowed_mentions=allowed_mentions,
        )

    # Attachments/images/files are sent separately
    for attachment in message.attachments:
        try:
            file = await attachment_to_file(attachment)

            await target_channel.send(
                content=header if ADD_HEADER else None,
                file=file,
                allowed_mentions=allowed_mentions,
            )

        except discord.HTTPException as e:
            log.error("Failed to forward attachment %s: %s", attachment.filename, e)


@bot.event
async def on_ready():
    log.info("Logged in as %s | Bot ID: %s", bot.user, bot.user.id)
    log.info("Source channels: %s", sorted(SOURCE_CHANNELS))
    log.info("Receiver channels: %s", sorted(RECEIVERS))
    log.info("Allowed senders: %s", sorted(ALLOWED_SENDERS))


@bot.event
async def on_message(message: discord.Message):
    # Prevent the bot from relaying its own messages
    if bot.user and message.author.id == bot.user.id:
        return

    # Only listen in configured LN source channel(s)
    if message.channel.id not in SOURCE_CHANNELS:
        await bot.process_commands(message)
        return

    # Avoid accidental loop if someone adds a receiver as source
    if message.channel.id in RECEIVERS:
        log.warning("Ignored message because source channel is also a receiver: %s", message.channel.id)
        await bot.process_commands(message)
        return

    # Only allow Shann, James, or the AI forwarder bot
    if not is_allowed_sender(message):
        log.info(
            "Ignored unauthorized sender: %s | User ID: %s | Channel ID: %s",
            message.author,
            message.author.id,
            message.channel.id,
        )
        await bot.process_commands(message)
        return

    for receiver_id in RECEIVERS:
        target_channel = await get_target_channel(receiver_id)

        if not target_channel:
            continue

        try:
            await forward_message(message, target_channel)
            log.info(
                "Relayed message from sender %s to receiver channel %s",
                message.author.id,
                receiver_id,
            )

        except discord.Forbidden:
            log.error("Missing permission to send to receiver channel %s", receiver_id)

        except discord.HTTPException as e:
            log.error("Discord API error for receiver channel %s: %s", receiver_id, e)

        except Exception:
            log.exception("Unexpected relay error for receiver channel %s", receiver_id)

    await bot.process_commands(message)


@bot.command()
async def ping(ctx):
    if not is_allowed_sender(ctx.message):
        return

    await ctx.reply("RektBot relay is online âœ…", mention_author=False)


bot.run(TOKEN)
