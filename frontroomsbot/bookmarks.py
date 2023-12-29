from discord import Embed, Colour, User, Message, DMChannel, Interaction, ButtonStyle
from discord.ui import Button, View, button
from datetime import datetime


class Bookmark:
    def __init__(self, author: User, message: Message, channel: DMChannel):
        self.author = author
        self.message = message
        self.channel = channel

        self.create_embed()
        self.view = BookmarkView()
        self.attachments = []
        self.files = []

    async def send(self):
        await self.channel.send(embed=self.embed, files=self.files, view=self.view)

    def create_embed(self):
        self.embed = Embed(
            title="Záložka!", description=self.message.jump_url, colour=Colour.purple()
        )

        self.embed.set_author(
            name=self.author.display_name, icon_url=self.author.avatar
        )

        time = datetime.now()
        self.embed.set_footer(text=f"Záložka vytvořena: {time}")

        if len(self.message.content) > 1024:
            content = self.message.content[:1025].split(" ")[0:-1]
            if len(content):
                self.split_words()
            else:
                self.split_string()

        else:
            self.embed.add_field(
                name="Obsah:", value=self.message.content, inline=False
            )

    def split_words(self):
        content = " ".join(self.message.content[:1025].split(" ")[0:-1])
        self.message.content = self.message.content[1025:]
        self.embed.add_field(name="Obsah:", value=content, inline=False)

        for i in range(len(self.message.content) // 1024 + 1):
            content = " ".join(self.message.content[:1025].split(" ")[0:-1])
            self.message.content = self.message.content[1025:]
            self.embed.add_field(name="", value=content, inline=True)

    def split_string(self):
        content = self.message.content[:1024]
        self.message.content = self.message.content[1024:]
        self.embed.add_field(name="Obsah:", value=content, inline=False)
        for i in range(len(self.message.content) // 1024 + 1):
            content = self.message.content[:1024]
            self.message.content = self.message.content[1024:]
            self.embed.add_field(name="", value=content, inline=True)

    async def add_media(self):
        if not self.message.attachments:
            return

        msg_attachments = self.message.attachments

        if "image" in msg_attachments[0].content_type and len(msg_attachments) == 1:
            self.embed.set_image(url=(msg_attachments.pop()).url)

        for attachment in msg_attachments:
            file = await attachment.to_file()
            self.files.append(file)


class BookmarkView(View):
    @button(label="Delete", style=ButtonStyle.danger, emoji="💥")
    async def delete_button(self, interaction: Interaction, button: Button):
        await interaction.message.delete()
