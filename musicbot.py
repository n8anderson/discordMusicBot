import asyncio

import discord as ds
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import youtube_dl as ydl

"""
Initial setup of discord bot, this connects to any server it is added to
and loads the intents (configuration profile) that the bot has
"""
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

intents = ds.Intents.all()
client = ds.Client(intents=intents)
musicBot = commands.Bot(command_prefix="-", intents=intents)

"""
Music extraction from youtube among other sites
this searches based on what the user inputs after the command prefix and command

TODO: Need to add options to select from a list of songs
"""
ydl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Might have to change to ipv4 address, needs testing
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = ydl.YoutubeDL(ytdl_format_options)


class YTDLSource(ds.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        filename = data['title'] if stream else ytdl.prepare_filename(data)
        return filename


"""
Bot Commands
"""


@musicBot.command(name='join', help='Forces the bot into the channel that the user is in',
                  aliases=['summon', 'j', 'come', 'here'])
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("{} is not in a voice channel. "
                       "Enter a voice channel to summon me".format(ctx.message.author.name))
    else:
        channel = ctx.message.author.voice.channel
        await channel.connect()


@musicBot.command(name='leave', help='Forces the bot to leave the connected channel',
                  aliases=['kick', 'drop', 'disconnect'])
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("I am not connected to any voice channels.")


@musicBot.command(name='play', help='Searches for and plays a song if found')
async def play(ctx):
    url = ctx.message.content[5:]

    try:
        server = ctx.message.guild
        voice_channel = server.voice_client

        async with ctx.typing():
            fileName = await YTDLSource.from_url(url, loop=musicBot.loop)
            voice_channel.play(ds.FFmpegPCMAudio(executable='bin\\ffmpeg.exe', source=fileName))
        await ctx.send("**Now playing: {}**".format(fileName))
    except Exception as E:
        print(str(E))
        await ctx.send("I am not connected to a voice channel.")


@musicBot.command(name='pause', help='Pauses the current song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client

    if voice_client.is_playing():
        await voice_client.pause()
        await ctx.send("Music paused.")
    else:
        await ctx.send("Nothing is playing at the moment.")


@musicBot.command(name='resume', help='Resumes the current song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client

    if voice_client.is_paused():
        voice_client.resume()
        await ctx.send("Music resumed.")
    else:
        await ctx.send('Nothing is paused or playing at the moment.')


@musicBot.command(name='stop', help='Stops the current song')
async def stop(ctx):
    voice_client = ctx.message.guild.voice_client

    if voice_client.is_paused() or voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Music stopped.")

    else:
        await ctx.send('I am doing nothing, what do you want from me.')


musicBot.run(TOKEN)
