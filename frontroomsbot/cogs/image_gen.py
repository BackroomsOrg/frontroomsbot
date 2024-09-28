import discord
from discord import app_commands
from bot import BackroomsBot
from ._config import ConfigCog, Cfg
from httpx_ws import aconnect_ws
import uuid
import base64
from io import BytesIO


def base64_to_bytes(uri: str) -> BytesIO:
    """
    'data:image/webp;base64,[bytes]
    """
    base64_raw = uri.split(",")[1].encode("ascii")
    return BytesIO(base64.b64decode(base64_raw))


class ImageGenCog(ConfigCog):
    api_key = Cfg(str)

    def __init__(self, bot: BackroomsBot) -> None:
        super().__init__(bot)

    @app_commands.command(
        name="generate_image", description="Generování obrázku z textového popisu"
    )
    async def generate_image(
        self,
        interaction: discord.Interaction,
        prompt: str,
        image_count: int = 1,
        width: int = 1024,
        height: int = 1024,
    ):
        await interaction.response.defer()
        async with aconnect_ws(
            "wss://ws-api.runware.ai/v1",
            # To avoid 403
            headers={
                "Origin": "https://fastflux.ai",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            },
        ) as ws:
            # Authenticate
            await ws.send_json(
                [
                    {
                        "taskType": "authentication",
                        "apiKey": await self.api_key,
                    }
                ]
            )
            # Wait for response
            await ws.receive_json()
            # Generate images
            await ws.send_json(
                [
                    {
                        "taskType": "imageInference",
                        "model": "runware:100@1",
                        "numberResults": image_count,
                        "outputFormat": "WEBP",
                        "outputType": ["dataURI", "URL"],
                        "positivePrompt": prompt,
                        "width": width,
                        "height": height,
                        "taskUUID": str(uuid.uuid4()),
                    }
                ]
            )
            # Wait for response
            images = []
            for _ in range(image_count):
                images.append(await ws.receive_json())
            # Convert to discord.File
            files = [
                discord.File(
                    fp=base64_to_bytes(image["data"][0]["imageDataURI"]),
                    filename=f"image{i}.webp",
                )
                for i, image in enumerate(images)
            ]
            # Send files
            await interaction.followup.send(files=files)


async def setup(bot: BackroomsBot) -> None:
    await bot.add_cog(ImageGenCog(bot), guild=bot.backrooms)
