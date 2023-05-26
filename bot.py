import discord
from discord.ext import commands
import unicodedata
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logging.info('Bot is starting up...')

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

intents = discord.Intents.all()
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

# Load banned usernames from config
banned_usernames = set(map(lambda u: {'type': 'exact', 'value': u} if isinstance(u, str) else u, config['banned_usernames']))

def save_banned_usernames():
    config['banned_usernames'] = list(banned_usernames)
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
    if any((username == ban['value'] if ban['type'] == 'exact' else ban['value'] in username)
           for ban in banned_usernames):
        await member.ban(reason='Banned username')

@bot.event
async def on_member_update(before, after):
    old_name = normalize_username(before.name)
    new_name = normalize_username(after.name)
    if old_name != new_name and any((new_name == ban['value'] if ban['type'] == 'exact' else ban['value'] in new_name)
                                    for ban in banned_usernames):
        await after.ban(reason='Banned username')

@bot.event
async def on_member_chunk(guild, members):
    for member in members:
        if any((normalize_username(member.name) == ban['value'] if ban['type'] == 'exact' else ban['value'] in normalize_username(member.name))
               for ban in banned_usernames):
            await member.ban(reason='Banned username')

def is_admin():
    async def predicate(ctx):
        admin_role_id = int(config["admin_role"])  # Get the admin role ID from config.json
        return any(role.id == admin_role_id for role in ctx.author.roles)
    return commands.check(predicate)

@bot.command()
@is_admin()
async def ban_username(ctx, username: str, match_type: str = 'exact'):
    global banned_usernames
    normalized_username = normalize_username(username)
    if match_type == 'exact':
        banned_usernames.add({'type': 'exact', 'value': normalized_username})
    elif match_type == 'contains':
        banned_usernames.add({'type': 'contains', 'value': normalized_username})
    else:
        await ctx.send(f'Invalid match_type. Must be "exact" or "contains".')
        return
    save_banned_usernames()
    await ctx.send(f'Username {username} has been added to the banned list.')

@bot.command()
@is_admin()
async def unban_username(ctx, username: str):
    logging.info(f'unban_username command invoked by {ctx.author} with argument {username}')
    normalized_username = normalize_username(username)
    for ban in banned_usernames.copy():
        if ban['value'] == normalized_username:
            banned_usernames.remove(ban)
    save_banned_usernames()
    await ctx.send(f'Username {username} has been removed from the banned list.')

@bot.command()
@is_admin()
async def sweep(ctx, exclude_roles: str = 'no'):
    report_channel_id = int(config["report_channel"])
    report_channel = bot.get_channel(report_channel_id)
    if not report_channel:
        await ctx.send('Report channel not found.')
        return
    exclude_roles = exclude_roles.lower() == 'yes'
    for guild in bot.guilds:
        for member in guild.members:
            if (not exclude_roles or all(role.is_default() for role in member.roles)) and any(
                    (normalize_username(member.name) == ban['value'] if ban['type'] == 'exact' else ban['value'] in normalize_username(member.name))
                    for ban in banned_usernames):
                await member.ban(reason='Banned username')
                await report_channel.send(f'Banned {member.name} ({member.id})')
    await ctx.send('Sweep complete.')

@bot.command()
async def list_banned_usernames(ctx):
    if banned_usernames:
        banned_list = '\n'.join(map(lambda u: u['value'], banned_usernames))
        await ctx.send(f'Banned usernames:\n{banned_list}')
    else:
        await ctx.send('No banned usernames.')

@bot.command()
async def helpnb(ctx):
    help_text = """
    **Commands:**
    `/ban_username <username> [match_type]` - Adds a username to the banned list. The `match_type` can be "exact" or "contains". Defaults to "exact". *Admin only*
    `/unban_username <username>` - Removes a username from the banned list. *Admin only*
    `/sweep [exclude_roles]` - Runs a sweep of all users and bans those with banned usernames. The `exclude_roles` can be "yes" or "no". Defaults to "no". If "yes", users with roles will be excluded. *Admin only*
    `/list_banned_usernames` - Lists all banned usernames.
    """
    await ctx.send(help_text)

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
