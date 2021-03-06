import asyncio
import warnings
import discord as ds
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import yt_dlp as ydl

"""
Initial setup of discord bot, this connects to any server it is added to
and loads the intents (configuration profile) that the bot has
"""
load_dotenv()
queued_songs = []
stopped = False
currently_playing = None
inUse = False

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
        return filename, data['title']


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
    server = ctx.message.guild
    voice_channel = server.voice_client
    if voice_channel.is_connected():
        await stop(ctx)
        await voice_channel.disconnect()
    else:
        await ctx.send("I am not connected to any voice channels.")


@musicBot.command(name='play', help='Searches for and plays a song if found')
async def play(ctx):
    global queued_songs
    global currently_playing
    global inUse
    url = ctx.message.content[5:]
    server = ctx.message.guild
    voice_channel = server.voice_client

    try:

        def next_song():
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                play_next(ctx, vc=voice_channel)

        async with ctx.typing():
            fileName, title = await YTDLSource.from_url(url, loop=musicBot.loop)
            if not voice_channel.is_playing():
                currently_playing = fileName
                voice_channel.play(ds.FFmpegPCMAudio(executable='bin\\ffmpeg.exe', source=fileName),
                                   after=lambda e: next_song())
                await ctx.send("**Now playing: {}**".format(title))
            else:
                queued_songs.append([fileName, title])
                await ctx.send("**{} Queued.**".format(title))
    except Exception as E:
        if not voice_channel:
            channel = ctx.message.author.voice.channel
            await channel.connect()
            await play(ctx)
        else:
            print(Exception, E)


def play_next(ctx, vc: ds.voice_client):
    global currently_playing
    global stopped

    def next_song():
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            play_next(ctx, vc=vc)

    if len(queued_songs) > 0 and not stopped:
        if vc.is_playing():
            vc.stop()
            asyncio.sleep(1)

        if os.path.exists(currently_playing):
            if currently_playing not in queued_songs[0]:
                os.remove(currently_playing)

        currently_playing, title = queued_songs.pop()
        vc.play(ds.FFmpegPCMAudio(executable='bin\\ffmpeg.exe', source=currently_playing),
                after=lambda e: next_song())
        asyncio.run_coroutine_threadsafe(ctx.send("**Now playing: {}**".format(title)), musicBot.loop)
    else:
        if os.path.exists(currently_playing):
            os.remove(currently_playing)
        asyncio.run_coroutine_threadsafe(ctx.send("Nothing to play."), musicBot.loop)


@musicBot.command(name='enqueue', help='Queues the requested song to be played.',
                  aliases=['queue', 'add', 'playnext'])
async def enqueue(ctx):
    global queued_songs
    server = ctx.message.guild
    voice_channel = server.voice_client

    url = ctx.message.content[5:]

    try:
        async with ctx.typing():
            fileName = await YTDLSource.from_url(url, loop=musicBot.loop)

            if voice_channel.is_playing():
                queued_songs.append(fileName)
                await ctx.send("{} has been added to the queue.".format(fileName))
            else:
                queued_songs.append(fileName)
                await play_next(ctx, vc=voice_channel)

    except Exception as E:
        print(Exception, E)
        await ctx.send("Something broke, check the console.")


@musicBot.command(name='skip', help='Skips the current song')
async def skip(ctx):
    server = ctx.message.guild
    voice_channel = server.voice_client
    if voice_channel.is_playing():
        if len(queued_songs) > 0:
            await play_next(ctx, vc=voice_channel)
        else:
            await ctx.send("Nothing to skip to.")


@musicBot.command(name='pause', help='Pauses the current song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client

    if voice_client.is_playing():
        await ctx.send("Music paused.")
        await voice_client.pause()
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


@musicBot.command(name='stop', help='Stops the current song and clears the queue',
                  aliases=['clear'])
async def stop(ctx):
    global currently_playing
    global stopped
    voice_client = ctx.message.guild.voice_client

    if voice_client.is_paused() or voice_client.is_playing():
        stopped = True
        voice_client.stop()
        await ctx.send("Music stopped.")

        if os.path.exists(currently_playing):
            os.remove(currently_playing)

        for collection in queued_songs:
            if os.path.exists(collection[0]):
                os.remove(collection[0])

    else:
        await ctx.send('I am doing nothing, what do you want from me.')


musicBot.run(TOKEN)
