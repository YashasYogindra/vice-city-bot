from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
import base64

import discord
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    PIL_AVAILABLE = True
except Exception:
    Image = ImageDraw = ImageFilter = ImageFont = ImageOps = None  # type: ignore[assignment]
    PIL_AVAILABLE = False

from vicecity.constants import HEAT_EMOJI, HEAT_STATUS, RACKS_EMOJI, TURF_EMOJI

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


MEDIA_STYLES: dict[str, dict[str, Any]] = {
    "join": {"title": "WELCOME TO VICE CITY", "bg": (18, 8, 33), "accent": (255, 84, 147)},
    "informant": {"title": "STREET CONTACT", "bg": (16, 12, 30), "accent": (92, 246, 255)},
    "drug_success": {"title": "STREET MONEY", "bg": (7, 37, 23), "accent": (0, 255, 153)},
    "drug_bust": {"title": "BUSTED", "bg": (40, 7, 7), "accent": (255, 55, 55)},
    "arms_success": {"title": "DEAL CLEARED", "bg": (10, 23, 35), "accent": (255, 215, 0)},
    "arms_bust": {"title": "WEAPONS STING", "bg": (48, 8, 8), "accent": (255, 0, 0)},
    "heat_5": {"title": "MOST WANTED", "bg": (49, 21, 0), "accent": (255, 80, 0)},
    "heist_live": {"title": "CASINO JOB LIVE", "bg": (4, 18, 44), "accent": (92, 246, 255)},
    "heist_success": {"title": "CLEAN GETAWAY", "bg": (14, 26, 33), "accent": (255, 215, 0)},
    "heist_fail": {"title": "LOCKDOWN", "bg": (43, 10, 10), "accent": (255, 65, 54)},
    "turf_win": {"title": "TURF TAKEN", "bg": (16, 25, 20), "accent": (54, 255, 116)},
    "turf_loss": {"title": "BLOCK LOST", "bg": (40, 12, 12), "accent": (255, 70, 70)},
    "slots_win": {"title": "SLOTS SPIKED", "bg": (26, 11, 37), "accent": (255, 215, 0)},
    "slots_loss": {"title": "SLOTS COLD", "bg": (39, 14, 23), "accent": (255, 70, 70)},
    "blackjack_win": {"title": "HOUSE SHAKEN", "bg": (11, 31, 26), "accent": (255, 215, 0)},
    "blackjack_loss": {"title": "HOUSE EDGE", "bg": (35, 10, 20), "accent": (255, 70, 70)},
    "event_police_sweep": {"title": "POLICE SWEEP", "bg": (40, 7, 7), "accent": (255, 55, 55)},
    "event_black_market_sale": {"title": "BLACK MARKET SALE", "bg": (18, 14, 6), "accent": (255, 215, 0)},
    "event_casino_rush": {"title": "CASINO RUSH", "bg": (26, 11, 37), "accent": (255, 180, 50)},
    "event_harbor_shipment": {"title": "HARBOR SHIPMENT", "bg": (4, 18, 30), "accent": (92, 246, 255)},
}


class VisualService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        asset_root = Path(__file__).resolve().parents[2] / "assets" / "fonts"
        self.font_candidates = (
            asset_root / "ViceCityDisplay-Bold.ttf",
            asset_root / "ViceCityDisplay-Regular.ttf",
            asset_root / "NotoSans-Bold.ttf",
            asset_root / "NotoSans-Regular.ttf",
            Path("C:/Windows/Fonts/impact.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        )

    async def build_profile_card(self, guild_id: int, user_id: int) -> tuple[discord.Embed, discord.File]:
        guild = self._get_guild(guild_id)
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise ValueError("Player profile not found.")
        member = guild.get_member(user_id)
        daily_status = None
        city_service = getattr(self.bot, "city_service", None)
        if city_service is not None:
            daily_status = city_service.get_daily_reward_status(player)
        if not PIL_AVAILABLE:
            embed = self.bot.embed_factory.standard(
                "Vice City Dossier",
                (
                    f"{member.mention if member else user_id} | Wallet {player['wallet']} | Heat {player['heat']} | "
                    f"Rank {player['rank']} | Streak {(daily_status or {}).get('current_streak', 0)}"
                ),
            )
            return embed, self._fallback_media_file("profile-card.png")
        gang = await self.bot.repo.get_gang(player["gang_id"]) if player.get("gang_id") else None
        inventory = await self.bot.repo.list_inventory(guild_id, user_id)
        canvas = Image.new("RGB", (960, 380), (12, 10, 24))
        draw = ImageDraw.Draw(canvas)
        accent = gang["role_id"] if gang else 0
        accent_color = self._pick_gang_color(gang)
        self._draw_gradient(canvas, (10, 10, 28), accent_color)
        draw.rounded_rectangle((24, 24, 936, 356), radius=28, outline=(255, 255, 255, 45), width=2)
        draw.rounded_rectangle((44, 44, 304, 336), radius=24, fill=(7, 8, 14, 180))
        avatar = await self._load_avatar(member, 240)
        canvas.paste(avatar, (54, 70), avatar)

        big = self._font(40, bold=True)
        medium = self._font(24, bold=True)
        body = self._font(20)
        small = self._font(16)
        draw.text((340, 60), member.display_name if member else str(user_id), font=big, fill=(255, 255, 255))
        draw.text((340, 112), f"Gang: {gang['name'] if gang else 'Independent'}", font=medium, fill=accent_color)
        draw.text((340, 152), f"Rank: {player['rank']}", font=body, fill=(255, 255, 255))
        draw.text((340, 184), f"{RACKS_EMOJI} Wallet: {player['wallet']}", font=body, fill=(255, 215, 0))
        draw.text((340, 216), f"{HEAT_EMOJI} Heat: {player['heat']}", font=body, fill=(255, 120, 120))
        streak_value = (daily_status or {}).get("current_streak", 0)
        draw.text((340, 248), f"XP: {player['xp']}   DAILY: {streak_value}-DAY STREAK", font=body, fill=(140, 240, 255))

        progress_start = (340, 292)
        progress_end = (860, 316)
        draw.rounded_rectangle((*progress_start, *progress_end), radius=12, fill=(28, 30, 46))
        next_threshold = self._next_rank_threshold(int(player["xp"]))
        if next_threshold is None:
            pct = 1.0
            progress_label = "City legend"
        else:
            previous_threshold = self._previous_rank_threshold(int(player["xp"]))
            span = max(1, next_threshold - previous_threshold)
            pct = min(1.0, max(0.0, (int(player["xp"]) - previous_threshold) / span))
            progress_label = f"Next rank at {next_threshold} XP"
        fill_right = progress_start[0] + int((progress_end[0] - progress_start[0]) * pct)
        draw.rounded_rectangle((progress_start[0], progress_start[1], fill_right, progress_end[1]), radius=12, fill=accent_color)
        draw.text((340, 322), progress_label, font=small, fill=(220, 225, 235))

        weapons = inventory.get("weapon", 0)
        burners = inventory.get("burnerphone", 0)
        lawyers = "Ready" if player.get("lawyer_cooldown_until") is None else "Cooling"
        draw.text((44, 26), "VICE CITY ID", font=medium, fill=(255, 255, 255))
        draw.text((56, 318), f"WEAPONS {weapons}   BURNERS {burners}   LAWYER {lawyers}", font=small, fill=(240, 240, 240))
        draw.text((720, 26), "NEON DOSSIER", font=small, fill=(220, 220, 230))

        card_file = self._to_file(canvas, "profile-card.png")
        embed = self.bot.embed_factory.standard("Vice City Dossier", "Your Vice City identity card is on file.")
        embed.set_image(url="attachment://profile-card.png")
        embed.add_field(name="Gang", value=gang["name"] if gang else "Independent", inline=True)
        embed.add_field(name="Rank", value=str(player["rank"]), inline=True)
        embed.add_field(name="Heat", value=str(player["heat"]), inline=True)
        if daily_status is not None:
            if daily_status["can_claim"]:
                daily_label = f"Ready now ({daily_status['reward_amount']} Racks)"
            else:
                daily_label = f"{daily_status['current_streak']}-day streak"
            embed.add_field(name="Daily", value=daily_label, inline=True)
        embed.add_field(name="Inventory", value=f"Weapons {weapons} | Burners {burners}", inline=False)
        if accent:
            embed.color = discord.Color(accent_color[0] << 16 | accent_color[1] << 8 | accent_color[2])
        return embed, card_file

    async def build_wanted_poster(
        self,
        guild_id: int,
        user_id: int,
        *,
        reason: str,
    ) -> tuple[discord.Embed, discord.File]:
        guild = self._get_guild(guild_id)
        player = await self.bot.repo.get_player(guild_id, user_id)
        if player is None:
            raise ValueError("Player profile not found.")
        member = guild.get_member(user_id)
        if not PIL_AVAILABLE:
            embed = self.bot.embed_factory.danger(
                "Wanted Poster",
                f"{member.mention if member else user_id} is marked wanted. Reason: {reason}",
            )
            return embed, self._fallback_media_file("wanted-poster.png")
        gang = await self.bot.repo.get_gang(player["gang_id"]) if player.get("gang_id") else None
        canvas = Image.new("RGB", (720, 980), (225, 207, 170))
        draw = ImageDraw.Draw(canvas)
        for offset in range(0, 720, 24):
            shade = 205 + (offset % 48)
            draw.rectangle((offset, 0, offset + 12, 980), fill=(shade, 188, 148))
        draw.rectangle((36, 36, 684, 944), outline=(111, 66, 34), width=6)
        title_font = self._font(64, bold=True)
        stamp_font = self._font(32, bold=True)
        body = self._font(28)
        small = self._font(22)
        draw.text((190, 70), "WANTED", font=title_font, fill=(80, 32, 18))
        draw.text((175, 138), "VICE CITY MOST WANTED", font=stamp_font, fill=(125, 56, 34))
        avatar = await self._load_avatar(member, 320)
        avatar = ImageOps.grayscale(avatar.convert("RGB")).convert("RGBA")
        avatar = avatar.filter(ImageFilter.SHARPEN)
        canvas.paste(avatar, (200, 220), avatar)
        bounty = max(500, int(player["wallet"]) // 2)
        draw.text((90, 575), f"NAME: {member.display_name if member else user_id}", font=body, fill=(55, 30, 19))
        draw.text((90, 620), f"GANG: {gang['name'] if gang else 'Independent'}", font=body, fill=(55, 30, 19))
        draw.text((90, 665), f"HEAT LEVEL: {player['heat']} / 5", font=body, fill=(55, 30, 19))
        draw.text((90, 710), f"BOUNTY: {RACKS_EMOJI} {bounty}", font=body, fill=(55, 30, 19))
        draw.multiline_text((90, 770), f"CAUSE:\n{reason}", font=small, fill=(55, 30, 19), spacing=10)
        stamp = Image.new("RGBA", (270, 110), (0, 0, 0, 0))
        stamp_draw = ImageDraw.Draw(stamp)
        stamp_draw.rounded_rectangle((6, 6, 264, 104), radius=18, outline=(160, 10, 10, 255), width=6)
        stamp_draw.text((44, 36), "MOST WANTED", font=stamp_font, fill=(160, 10, 10, 255))
        stamp = stamp.rotate(-12, expand=True)
        canvas.paste(stamp, (390, 655), stamp)

        poster_file = self._to_file(canvas, "wanted-poster.png")
        embed = self.bot.embed_factory.danger("Wanted Poster", f"{member.mention if member else user_id} just hit Heat 5.")
        embed.set_image(url="attachment://wanted-poster.png")
        embed.add_field(name="Gang", value=gang["name"] if gang else "Independent", inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        status = HEAT_STATUS.get(int(player["heat"]), ("Unknown", ""))[0]
        embed.add_field(name="Status", value=status, inline=True)
        return embed, poster_file

    async def build_heist_result_card(
        self,
        *,
        guild_id: int,
        heist: dict[str, Any],
        outcome_title: str,
        outcome_description: str,
        payout_total: int,
        crew_results: list[tuple[str, str, bool]],
    ) -> tuple[discord.Embed, discord.File]:
        guild = self._get_guild(guild_id)
        if not PIL_AVAILABLE:
            embed = self.bot.embed_factory.reward(outcome_title, outcome_description)
            if "Failed" in outcome_title:
                embed = self.bot.embed_factory.danger(outcome_title, outcome_description)
            return embed, self._fallback_media_file("heist-result.png")
        canvas = Image.new("RGB", (1100, 560), (8, 20, 36))
        self._draw_gradient(canvas, (7, 16, 36), (12, 83, 128))
        draw = ImageDraw.Draw(canvas)
        title_font = self._font(46, bold=True)
        role_font = self._font(24, bold=True)
        body = self._font(22)
        small = self._font(18)
        draw.text((38, 32), outcome_title.upper(), font=title_font, fill=(255, 255, 255))
        draw.text((40, 94), outcome_description, font=body, fill=(214, 229, 244))
        draw.text((38, 142), f"{RACKS_EMOJI} TAKE {payout_total}", font=role_font, fill=(255, 215, 0))
        draw.text((850, 34), "CASINO JOB FILE", font=small, fill=(135, 225, 255))

        left = 40
        for index, (role_name, member_name, success) in enumerate(crew_results):
            column_left = left + index * 340
            fill = (34, 130, 84) if success else (140, 30, 30)
            draw.rounded_rectangle((column_left, 200, column_left + 300, 484), radius=24, fill=(13, 25, 40), outline=fill, width=4)
            user_id = heist.get(f"{role_name}_id")
            member = guild.get_member(user_id) if user_id else None
            avatar = await self._load_avatar(member, 118)
            canvas.paste(avatar, (column_left + 92, 226), avatar)
            draw.text((column_left + 26, 362), role_name.upper(), font=role_font, fill=fill)
            draw.text((column_left + 26, 399), member_name, font=body, fill=(250, 250, 250))
            draw.text((column_left + 26, 434), "SUCCESS" if success else "FAILED", font=role_font, fill=fill)

        card_file = self._to_file(canvas, "heist-result.png")
        embed = self.bot.embed_factory.reward(outcome_title, outcome_description)
        if "Failed" in outcome_title:
            embed = self.bot.embed_factory.danger(outcome_title, outcome_description)
        embed.set_image(url="attachment://heist-result.png")
        return embed, card_file

    async def build_event_banner(self, media_key: str, *, subtitle: str = "") -> discord.File | None:
        style = MEDIA_STYLES.get(media_key)
        if style is None:
            return None
        if not PIL_AVAILABLE:
            return self._fallback_media_file(f"{media_key}.png")
        title = style["title"]
        bg = style["bg"]
        accent = style["accent"]
        frames: list[Image.Image] = []
        width, height = 760, 250
        title_font = self._font(40, bold=True)
        subtitle_font = self._font(20, bold=False)
        for frame_index in range(6):
            frame = Image.new("P", (width, height))
            canvas = Image.new("RGBA", (width, height), (*bg, 255))
            draw = ImageDraw.Draw(canvas)
            pulse = 40 + frame_index * 22
            draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=24, outline=(*accent, 255), width=4)
            draw.rectangle((28, 34, width - 28, 78), fill=(*accent, min(255, pulse + 50)))
            for offset in range(0, width, 60):
                draw.line((offset, 0, offset + frame_index * 9, height), fill=(255, 255, 255, 28), width=2)
            draw.text((42, 34), title, font=title_font, fill=(12, 12, 12))
            if subtitle:
                draw.text((44, 116), subtitle[:48], font=subtitle_font, fill=(255, 255, 255))
            draw.text((44, 168), "VICE CITY OS", font=subtitle_font, fill=accent)
            frame = canvas.convert("P", palette=Image.ADAPTIVE)
            frames.append(frame)
        buffer = BytesIO()
        frames[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=110,
            loop=0,
            disposal=2,
        )
        buffer.seek(0)
        return discord.File(buffer, filename=f"{media_key}.gif")

    def _get_guild(self, guild_id: int) -> discord.Guild:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise RuntimeError(f"Guild {guild_id} is not available.")
        return guild

    async def _load_avatar(self, member: discord.Member | None, size: int) -> Image.Image:
        image = Image.new("RGBA", (size, size), (30, 34, 44, 255))
        if member is not None:
            try:
                payload = await member.display_avatar.replace(size=max(64, size)).read()
                avatar = Image.open(BytesIO(payload)).convert("RGBA").resize((size, size))
                image = avatar
            except Exception:
                pass
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, size - 1, size - 1), fill=255)
        rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded.paste(image, (0, 0), mask)
        return rounded

    def _draw_gradient(self, image: Image.Image, start: tuple[int, int, int], accent: tuple[int, int, int]) -> None:
        width, height = image.size
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for index in range(height):
            ratio = index / max(1, height - 1)
            r = int(start[0] * (1 - ratio) + accent[0] * ratio * 0.5)
            g = int(start[1] * (1 - ratio) + accent[1] * ratio * 0.5)
            b = int(start[2] * (1 - ratio) + accent[2] * ratio * 0.5)
            draw.line((0, index, width, index), fill=(r, g, b, 255))
        image.paste(overlay, (0, 0), overlay)

    def _pick_gang_color(self, gang: dict[str, Any] | None) -> tuple[int, int, int]:
        if not gang:
            return (0, 223, 184)
        name = str(gang["name"]).lower()
        if "serpent" in name:
            return (53, 203, 112)
        if "wolf" in name:
            return (198, 205, 215)
        if "syndicate" in name:
            return (64, 205, 224)
        if "cartel" in name:
            return (255, 189, 50)
        return (255, 84, 147)

    def _next_rank_threshold(self, xp: int) -> int | None:
        for threshold in (500, 1500, 3000, 6000):
            if xp < threshold:
                return threshold
        return None

    def _previous_rank_threshold(self, xp: int) -> int:
        previous = 0
        for threshold in (500, 1500, 3000, 6000):
            if xp < threshold:
                return previous
            previous = threshold
        return previous

    def _font(self, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is unavailable.")
        resolved = self._resolve_font_path(bold=bold)
        if resolved is not None:
            try:
                return ImageFont.truetype(str(resolved), size=size)
            except OSError:
                pass
        for path in self.font_candidates:
            if path == resolved or not path.exists():
                continue
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _resolve_font_path(self, *, bold: bool = False) -> Path | None:
        bold_markers = ("bold", "bd", "black", "heavy", "impact")
        preferred: list[Path] = []
        fallback: list[Path] = []
        for candidate in self.font_candidates:
            if not candidate.exists():
                continue
            lowered = candidate.name.lower()
            has_bold_marker = any(marker in lowered for marker in bold_markers)
            if bold and has_bold_marker:
                preferred.append(candidate)
            elif not bold and not has_bold_marker:
                preferred.append(candidate)
            else:
                fallback.append(candidate)
        if preferred:
            return preferred[0]
        if fallback:
            return fallback[0]
        return None

    def _to_file(self, image: Image.Image, filename: str) -> discord.File:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename=filename)

    def _fallback_media_file(self, filename: str) -> discord.File:
        png_base64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+cP6kAAAAASUVORK5CYII="
        )
        data = base64.b64decode(png_base64)
        return discord.File(BytesIO(data), filename=filename)
