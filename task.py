import discord
from discord.ext import commands, tasks
from discord.utils import get
from datetime import datetime
import asyncio

# Replace with your bot token
TOKEN = "YOUR_BOT_TOKEN"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="%", intents=intents)

# Task tracking and leaderboard data
tasks_in_progress = {}
leaderboard = {}
leaderboard_message = None  # Reference to the leaderboard message


@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await setup_leaderboard()  # Setup the leaderboard when the bot starts
    update_leaderboard.start()  # Start the background task


@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Create leaderboard and task chat channels."""
    guild = ctx.guild
    leaderboard_channel = get(guild.channels, name="leaderboard")
    task_chat_channel = get(guild.channels, name="task-chat")

    if not leaderboard_channel:
        leaderboard_channel = await guild.create_text_channel("leaderboard")
    if not task_chat_channel:
        task_chat_channel = await guild.create_text_channel("task-chat")

    await ctx.send("Setup completed: `leaderboard` and `task-chat` channels created.")


async def setup_leaderboard():
    """Set up the leaderboard channel with a fixed message."""
    global leaderboard_message

    for guild in bot.guilds:
        leaderboard_channel = get(guild.channels, name="leaderboard")
        if leaderboard_channel:
            async for message in leaderboard_channel.history(limit=10):
                if message.author == bot.user:
                    leaderboard_message = message
                    break
            else:
                leaderboard_message = await leaderboard_channel.send("Initializing leaderboard...")  # Create a new message

            await update_leaderboard()  # Update leaderboard immediately
            break


@tasks.loop(minutes=1)
async def update_leaderboard():
    """Update the leaderboard every 15 minutes."""
    global leaderboard_message

    for guild in bot.guilds:
        leaderboard_channel = get(guild.channels, name="leaderboard")
        if not leaderboard_channel or not leaderboard_message:
            continue

        if leaderboard_message.author != bot.user:
            leaderboard_message = await leaderboard_channel.send("Initializing leaderboard...")

        required_roles = ["Staff", "Moderator"]
        leaderboard_embed = discord.Embed(
            title="🏆 **Leaderboard** 🏆",
            description="**Top Staff Members and Their Task Completion Stats**",
            color=discord.Color.gold(),
        )
        leaderboard_embed.set_thumbnail(url="https://example.com/leaderboard_image.png")  # Optional thumbnail

        if not leaderboard:
            leaderboard_embed.add_field(
                name="No Data Yet",
                value="Tasks have not been completed yet. Start using `%task`!",
                inline=False
            )
        else:
            for member_id, score in sorted(leaderboard.items(), key=lambda item: item[1], reverse=True):
                member = guild.get_member(member_id)
                if member and any(role.name in required_roles for role in member.roles):
                    leaderboard_embed.add_field(
                        name=f"🎖️ {member.display_name}",
                        value=f"**Tasks Completed:** {score} 🏅",
                        inline=False
                    )

        leaderboard_embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await leaderboard_message.edit(content=None, embed=leaderboard_embed)



@bot.command()
async def task(ctx):
    """Handle the %task command."""
    required_roles = ["Staff", "Moderator"]
    user_roles = [role.name for role in ctx.author.roles]

    if not any(role in required_roles for role in user_roles):
        await ctx.message.add_reaction("❌")
        await send_task_status(ctx, ctx.author, "❌ Task failed: You do not have the required role.")
        return

    if not ctx.author.voice:
        await ctx.message.add_reaction("❌")
        await send_task_status(ctx, ctx.author, "❌ Task failed: You are not in a voice channel.")
        return

    vc = ctx.author.voice.channel
    staff_members = [member for member in vc.members if any(role.name in required_roles for role in member.roles)]
    non_staff_members = [member for member in vc.members if member not in staff_members]

    if len(non_staff_members) < 1:
        await ctx.message.add_reaction("❌")
        await send_task_status(ctx, ctx.author, "❌ Task failed: Not enough participants (1 per staff required).")
        return

    now = datetime.now()
    tasks_in_progress[ctx.author.id] = {"start_time": now, "vc": vc, "members": vc.members}

    await ctx.message.add_reaction("✅")
    await send_task_status(ctx, ctx.author, "✅ Task started! I'll verify completion in 1 minutes.")

    await asyncio.sleep(1 * 60)

    task_data = tasks_in_progress.pop(ctx.author.id, None)
    if not task_data or task_data["vc"] != vc:
        await send_task_status(ctx, ctx.author, "❌ Task failed: Voice channel conditions changed.")
        return

    leaderboard[ctx.author.id] = leaderboard.get(ctx.author.id, 0) + 1
    await send_task_status(ctx, ctx.author, "✅ Task successfully completed!", vc)


async def send_task_status(ctx, author, message, vc=None):
    """Send detailed task status to the task-chat channel."""
    task_chat_channel = get(ctx.guild.channels, name="task-chat")
    if not task_chat_channel:
        return

    embed = discord.Embed(
        title="Task Status",
        description=message,
        color=discord.Color.green() if "✅" in message else discord.Color.red(),
    )
    embed.add_field(name="**Staff Member**", value=author.mention, inline=False)
    if vc:
        embed.add_field(
            name="**Participants**",
            value=", ".join([member.mention for member in vc.members]),
            inline=False,
        )
        embed.add_field(name="**Voice Channel**", value=vc.name, inline=False)
    embed.set_footer(text=f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await task_chat_channel.send(embed=embed)


bot.run("token")
