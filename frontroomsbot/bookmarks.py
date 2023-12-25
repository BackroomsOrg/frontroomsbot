from discord import Embed, Colour, User, Message, Attachment, DMChannel
from datetime import datetime
from typing import List

class Bookmark:
    def __init__(self, author: User, message: Message, channel:DMChannel):
        self.author = author
        self.message = message
        self.channel = channel

        self.embed = self.create_embed()
        self.attachments = []
        self.files = []

    async def send(self):
        await self.channel.send(embed=self.embed, files=self.files)


    def create_embed(self):
        embed = Embed(
            title="Záložka!", description=self.message.jump_url, colour=Colour.purple()
        )

        embed.set_author(name=self.author.display_name, icon_url=self.author.avatar)

        time = datetime.now()
        embed.set_footer(text=f"Záložka vytvořena: {time}")

        embed.add_field(name="Obsah:", value=self.message.content, inline=False)

        return embed

    async def add_media(self):
        if not self.message.attachments:
            return

        msg_attachments = self.message.attachments

        if "image" in msg_attachments[0].content_type and len(msg_attachments) == 1:
            self.embed.set_image(url=(msg_attachments.pop()).url)

        for attachment in msg_attachments:
            file = await attachment.to_file()
            self.files.append(file)

