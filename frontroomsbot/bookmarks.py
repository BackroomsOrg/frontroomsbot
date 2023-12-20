from discord import Embed, Colour, User, Message, Attachment
from datetime import datetime
from typing import List


def get_bookmark(author: User, message: Message) -> Embed:
    bookmark = Embed(
        title="Záložka!", description=message.jump_url, colour=Colour.purple()
    )

    bookmark.set_author(name=author.display_name, icon_url=author.avatar)

    time = datetime.now()
    bookmark.set_footer(text=f"Záložka vytvořena: {time}")

    bookmark.add_field(name="Obsah:", value=message.content, inline=False)
    if message.attachments:
        add_media(bookmark, message.attachments)

    return bookmark


def add_media(bookmark: Embed, attachments: List[Attachment]):
    if len(attachments) > 1:
        bookmark.add_field(name="", value="[Info] Zpráva ma více příloh!", inline=False)

    if "image" in attachments[0].content_type:
        bookmark.set_image(url=attachments[0].url)
    else:
        bookmark.add_field(name="", value=attachments[0].url)
