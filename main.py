import discord
import os

client = discord.Client(intents=discord.Intents.all())

@client.event
async def on_ready():
    print(f'Bot is online as {client.user}')

@client.event
async def on_message(message):
    if message.content == "!ping":
        await message.channel.send("Pong!")

client.run(os.getenv("MTQ5NjE0OTM5NTcyNzU4NTM4MQ.G3Q0J7.DvIiAFWv-36NykQvJI3IKXlgA1pt3yKXCZkZAo"))
