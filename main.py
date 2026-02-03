import logging
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from discord.utils import setup_logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import commands as command_functions
import jobs as job_functions
from box import Box
import pytz
import yaml

# First, setup logging
setup_logging(level=logging.INFO)  # you can also use DEBUG, WARNING, etc.

# Load from .env file if needed
load_dotenv()

# Now get a logger instance
logger = logging.getLogger(__name__)  # typically use __name__ for module/class

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

async def register_commands(config, bot):
    try:
        # Register commands
        groups = {
            group_name: app_commands.Group(name=group_name, description=group_name.upper())
            for group_name in [command.group for command in config.bot.commands]
        }

        for command_config in config.bot.commands:
            func = getattr(command_functions, command_config.func_name)
            groups.get(command_config.group).command(name=command_config.name, description=command_config.description)(func)
            logger.info("Added %s command (%s)", command_config.name, command_config.description)

        for group in groups.values():
            bot.tree.add_command(group)

        synced = await bot.tree.sync()
        logger.info("Synced %s slash commands", len(synced))
    except Exception as e:
        logger.exception("Error syncing commands")

def register_jobs(config):
    timezone = pytz.timezone(config.bot.timezone)
    scheduler = AsyncIOScheduler(timezone=timezone)

    # Register cron jobs
    for job_config in config.bot.jobs:
        trigger = CronTrigger.from_crontab(job_config.interval, timezone=timezone)
        func = getattr(job_functions, job_config.func_name)
        job_instance = scheduler.add_job(func, trigger, args=[bot, config])
        logger.info("Scheduled %s job (%s). Next run time at %s", job_config.name, job_config.description, job_instance.trigger.get_next_fire_time(None, datetime.now(timezone)))
        
    if not scheduler.running:
        scheduler.start()

@bot.event
async def on_ready():
    logger.info("Bot connected as %s", bot.user)

    logger.info("Bot reading config")
    # Try read config
    with open("config.yml", "r") as f:
        config = Box(yaml.safe_load(f))

    bot.config = config
    await register_commands(config, bot)
    register_jobs(config)
    logger.info("Bot ready")

if __name__ == "__main__":
    bot.run(TOKEN)