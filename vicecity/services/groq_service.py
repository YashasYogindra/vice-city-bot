from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from vicecity.models.cinematic import GroqInformantTipResult, GroqNarrationResult, GroqNegotiationResult
from vicecity.models.events import GroqCityEventResult

if TYPE_CHECKING:
    from vicecity.bot import ViceCityBot


class GroqService:
    def __init__(self, bot: "ViceCityBot") -> None:
        self.bot = bot
        self.logger = logging.getLogger("vicecity.groq")
        self.last_request_status = "No Groq request yet."

    async def generate_bust_negotiation(
        self,
        *,
        member_name: str,
        gang_name: str,
        operation_name: str,
        risk: str,
        approach: str,
        plea_text: str,
        allowed_outcomes: tuple[str, ...],
    ) -> GroqNegotiationResult:
        fallback = self._fallback_negotiation(
            member_name=member_name,
            gang_name=gang_name,
            operation_name=operation_name,
            approach=approach,
            allowed_outcomes=allowed_outcomes,
        )
        payload = {
            "member_name": member_name,
            "gang_name": gang_name,
            "operation_name": operation_name,
            "risk": risk,
            "approach": approach,
            "plea_text": plea_text,
            "allowed_outcomes": list(allowed_outcomes),
        }
        prompt = (
            "You are writing a dramatic Vice City police negotiation scene for a Discord bot. "
            "Return strict JSON only with keys outcome, headline, scene, officer_line. "
            "The outcome must be exactly one of the allowed outcomes. "
            "Keep the tone cinematic, sharp, and under 70 words per field.\n\n"
            f"Context: {json.dumps(payload, ensure_ascii=True)}"
        )
        text = await self._generate_json_text(prompt)
        if text is None:
            return fallback
        try:
            raw = self._parse_json(text)
            outcome = str(raw.get("outcome", "")).strip()
            headline = str(raw.get("headline", "")).strip()
            scene = str(raw.get("scene", "")).strip()
            officer_line = str(raw.get("officer_line", "")).strip()
            if outcome not in allowed_outcomes:
                raise ValueError(f"Unsupported outcome: {outcome}")
            if not headline or not scene or not officer_line:
                raise ValueError("Incomplete Groq negotiation payload")
            return GroqNegotiationResult(
                outcome=outcome,
                headline=headline,
                scene=scene,
                officer_line=officer_line,
            )
        except Exception:
            self.last_request_status = "Fallback used: invalid Groq negotiation JSON."
            self.logger.exception("Failed to parse Groq bust negotiation payload")
            return fallback

    async def generate_heist_narration(
        self,
        *,
        phase: str,
        gang_name: str,
        crew_names: list[str],
        success_count: int | None = None,
        payout_total: int | None = None,
    ) -> GroqNarrationResult:
        fallback = self._fallback_heist(
            phase=phase,
            gang_name=gang_name,
            crew_names=crew_names,
            success_count=success_count,
            payout_total=payout_total,
        )
        payload = {
            "phase": phase,
            "gang_name": gang_name,
            "crew_names": crew_names,
            "success_count": success_count,
            "payout_total": payout_total,
        }
        prompt = (
            "You are narrating a cinematic Vice City casino heist for Discord. "
            "Return strict JSON only with keys headline and lines. "
            "lines must be an array of 2 or 3 dramatic one-sentence updates. "
            "Keep each line under 25 words, punchy, and PG-13.\n\n"
            f"Context: {json.dumps(payload, ensure_ascii=True)}"
        )
        text = await self._generate_json_text(prompt)
        if text is None:
            return fallback
        try:
            raw = self._parse_json(text)
            headline = str(raw.get("headline", "")).strip()
            lines = [str(line).strip() for line in raw.get("lines", []) if str(line).strip()]
            if not headline or not lines:
                raise ValueError("Incomplete Groq heist payload")
            return GroqNarrationResult(headline=headline, lines=lines[:3])
        except Exception:
            self.last_request_status = "Fallback used: invalid Groq heist JSON."
            self.logger.exception("Failed to parse Groq heist narration payload")
            return fallback

    async def generate_informant_tip(
        self,
        *,
        focus: str,
        facts: list[str],
        fallback: GroqInformantTipResult,
    ) -> GroqInformantTipResult:
        payload = {
            "focus": focus,
            "facts": facts,
        }
        prompt = (
            "You are a cryptic Vice City street informant speaking inside a Discord crime game. "
            "Return strict JSON only with keys headline, tip, nudge. "
            "Use only the supplied facts. Do not invent numbers or events. "
            "Keep it cinematic, actionable, under 45 words per field, and sound like whispered street intel.\n\n"
            f"Context: {json.dumps(payload, ensure_ascii=True)}"
        )
        text = await self._generate_json_text(prompt)
        if text is None:
            return fallback
        try:
            raw = self._parse_json(text)
            headline = str(raw.get("headline", "")).strip()
            tip = str(raw.get("tip", "")).strip()
            nudge = str(raw.get("nudge", "")).strip()
            if not headline or not tip or not nudge:
                raise ValueError("Incomplete Groq informant payload")
            return GroqInformantTipResult(headline=headline, tip=tip, nudge=nudge)
        except Exception:
            self.last_request_status = "Fallback used: invalid Groq informant JSON."
            self.logger.exception("Failed to parse Groq informant payload")
            return fallback

    async def generate_city_event_copy(
        self,
        *,
        event_name: str,
        vibe: str,
        mechanics: list[str],
        fallback: GroqCityEventResult,
    ) -> GroqCityEventResult:
        payload = {
            "event_name": event_name,
            "vibe": vibe,
            "mechanics": mechanics,
        }
        prompt = (
            "You are writing a flashy Vice City citywide event bulletin for a Discord crime game. "
            "Return strict JSON only with keys headline, description, broadcast. "
            "Do not invent mechanics outside the supplied list. "
            "Keep each field under 45 words, cinematic, and instantly understandable to players.\n\n"
            f"Context: {json.dumps(payload, ensure_ascii=True)}"
        )
        text = await self._generate_json_text(prompt)
        if text is None:
            return fallback
        try:
            raw = self._parse_json(text)
            headline = str(raw.get("headline", "")).strip()
            description = str(raw.get("description", "")).strip()
            broadcast = str(raw.get("broadcast", "")).strip()
            if not headline or not description or not broadcast:
                raise ValueError("Incomplete Groq city event payload")
            return GroqCityEventResult(headline=headline, description=description, broadcast=broadcast)
        except Exception:
            self.last_request_status = "Fallback used: invalid Groq city event JSON."
            self.logger.exception("Failed to parse Groq city event payload")
            return fallback

    async def _generate_json_text(self, prompt: str) -> str | None:
        api_key = self.bot.config.groq_api_key
        if not api_key:
            self.last_request_status = "Fallback used: GROQ_API_KEY is not set."
            return None
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.bot.config.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "top_p": 0.95,
            "response_format": {"type": "json_object"},
        }
        timeout = aiohttp.ClientTimeout(total=8)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=body) as response:
                    if response.status >= 400:
                        self.last_request_status = f"Fallback used: Groq HTTP {response.status}."
                        self.logger.warning("Groq request failed with status %s", response.status)
                        try:
                            error_data = await response.text()
                            self.logger.warning(f"Groq API error details: {error_data}")
                        except Exception:
                            pass
                        return None
                    payload = await response.json()
        except Exception as exc:
            self.last_request_status = f"Fallback used: {type(exc).__name__} during Groq request."
            self.logger.exception("Groq request failed")
            return None
        text = self._extract_text(payload)
        if text is None:
            self.last_request_status = "Fallback used: Groq returned no text."
            return None
        self.last_request_status = "Groq request succeeded."
        return text

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        choices = payload.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        text = message.get("content")
        if text:
            return str(text)
        return None

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        return json.loads(cleaned[start : end + 1])

    def _fallback_negotiation(
        self,
        *,
        member_name: str,
        gang_name: str,
        operation_name: str,
        approach: str,
        allowed_outcomes: tuple[str, ...],
    ) -> GroqNegotiationResult:
        approach = approach.lower()
        preferred = {
            "plead": "reduced_fine",
            "bribe": "reduced_fine",
            "bluff": "deal_rejected",
            "threaten": "extra_heat",
        }.get(approach, "deal_rejected")
        outcome = preferred if preferred in allowed_outcomes else allowed_outcomes[0]
        return GroqNegotiationResult(
            outcome=outcome,
            headline="Interrogation Room",
            scene=(
                f"The desk sergeant studies {member_name}'s face, drums two fingers on the file, "
                f"and weighs the story coming out of {gang_name}'s latest {operation_name} mess."
            ),
            officer_line="Talk fast. Vice City is deciding how expensive this mistake becomes.",
        )

    def _fallback_heist(
        self,
        *,
        phase: str,
        gang_name: str,
        crew_names: list[str],
        success_count: int | None,
        payout_total: int | None,
    ) -> GroqNarrationResult:
        joined = ", ".join(crew_names) if crew_names else "the crew"
        if phase == "launch":
            return GroqNarrationResult(
                headline="Casino Job Live",
                lines=[
                    f"{gang_name} just kicked the doors in and {joined} are moving on the vault.",
                    "Vice City cameras are jittering, alarms are humming, and the whole city can feel it.",
                    "Every second from here on out looks like it was cut from a crime movie.",
                ],
            )
        return GroqNarrationResult(
            headline="Casino Job Recap",
            lines=[
                f"{gang_name} left the casino with {success_count or 0} clean role hits and a take of {payout_total or 0}.",
                "The city is already rewriting the story into legend, rumor, and panic.",
            ],
        )
