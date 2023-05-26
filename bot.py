import discord
from discord.ext import commands
import unicodedata
import json
import logging
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.info('Bot is starting up...')

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Ensure that banned_usernames is a list
banned_usernames = config.get('banned_usernames', [])
if not isinstance(banned_usernames, list):
    banned_usernames = [banned_usernames]

# Convert banned_usernames to a set
banned_usernames_set = set(banned_usernames)

intents = discord.Intents.all()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

def save_banned_usernames():
    banned_usernames_list = list(banned_usernames_set)
    config['banned_usernames'] = banned_usernames_list
    with open('config.json', 'w') as f:
        json.dump(config, f)

def normalize_username(username):
    return ''.join(
        c for c in unicodedata.normalize('NFKD', username)
        if not unicodedata.combining(c)
    ).lower()

@bot.event
async def on_ready():
    logging.info(f'{bot.user} has connected to Discord!')

@bot.event
async def on_member_join(member):
    username = normalize_username(member.name)
    if username in banned_usernames_set:
        await member.ban(reason='Banned username')

@bot.event
async def on_member_update(before, after):
    old_name = normalize_username(before.name)
    new_name = normalize_username(after.name)
    if old_name != new_name and new_name in banned_usernames_set:
        await after.ban(reason='Banned username')

@bot.event
async def on_member_chunk(guild, members):
    for member in members:
        if normalize_username(member.name) in banned_usernames_set:
            await member.ban(reason='Banned username')

def is_admin():
    async def predicate(ctx):
        admin_role_id = int(config["admin_role"])  # Get the admin role ID from config.json
        return any(role.id == admin_role_id for role in ctx.author.roles)
    return commands.check(predicate)

@bot.command()
@is_admin()
async def ban_username(ctx, username: str):
    global banned_usernames_set
    normalized_username = normalize_username(username)
    banned_usernames_set.add(normalized_username)
    save_banned_usernames()
    await ctx.send(f'Username {username} has been added to the banned list.')

@bot.command()
@is_admin()
async def unban_username(ctx, username: str):
    global banned_usernames_set
    logging.info(f'unban_username command invoked by {ctx.author} with argument {username}')
    normalized_username = normalize_username(username)
    if normalized_username in banned_usernames_set:
        banned_usernames_set.remove(normalized_username)
        save_banned_usernames()
        await ctx.send(f'Username {username} has been removed from the banned list.')
    else:
        await ctx.send(f'Username {username} is not in the banned list.')

@bot.command()
@is_admin()
async def sweep(ctx, *, option=None):
    report_channel_id = int(config["report_channel"])
    report_channel = bot.get_channel(report_channel_id)
    if not report_channel:
        await ctx.send('Report channel not found.')
        return
    for guild in bot.guilds:
        members = guild.members
        while members:
            chunk = members[:1000]
            members = members[1000:]
            for member in chunk:
                if option == 'no_roles':
                    if member.roles == [guild.default_role]:
                        for banned_username in banned_usernames_set:
                            if banned_username in normalize_username(member.name):
                                await member.ban(reason='Banned username')
                                await report_channel.send(f'Banned {member.name} ({member.id})')
                else:
                    for banned_username in banned_usernames_set:
                        if banned_username in normalize_username(member.name):
                            await member.ban(reason='Banned username')
                            await report_channel.send(f'Banned {member.name} ({member.id})')
            await asyncio.sleep(1)
    await ctx.send('Sweep complete.')

@bot.command()
async def list_banned_usernames(ctx):
    if banned_usernames_set:
        banned_list = '\n'.join(ban for ban in banned_usernames_set)
        await ctx.send(f'Banned usernames:\n{banned_list}')
    else:
        await ctx.send('No banned usernames.')

@bot.command()
async def helpnb(ctx):
    help_text = """
    **Commands:**
    `!ban_username <username>` - Adds a username to the banned list. *Admin only*
    `!unban_username <username>` - Removes a username from the banned list. *Admin only*
    `!list_banned_usernames` - Lists all banned usernames.
    """
    await ctx.send(help_text)

@ban_username.error
async def ban_username_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Please specify a username to ban.')
    else:
        logging.error(f'An unhandled exception occurred: {error}')  # Log the error for debugging
        await ctx.send('An unexpected error occurred.')

@unban_username.error
async def unban_username_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Please specify a username to unban.')
    else:
        logging.error(f'An unhandled exception occurred: {error}')  # Log the error for debugging
        await ctx.send('An unexpected error occurred.')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send('You do not have permission to use this command.')
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send('Command not found.')
    else:
        logging.error(f'An unhandled exception occurred: {error}')  # Log the error for debugging
        await ctx.send('An unexpected error occurred.')

bot.run(config['bot_token'])
