"""
Argus Omega — Autonomous Scanner
ScriptMasterLabs™

Background loop that scans conviction tickers through the Omega Fusion Engine
and pushes high-conviction signals to Discord. Converts Argus from a passive
API into an active intelligence provider.
"""
import asyncio
import logging
import os
import random
from datetime import datetime, timezone, timedelta

import aiohttp
import httpx

from app.config import (
    CI_EXTREME_THRESH, CI_HIGH_THRESH, CI_MODERATE_THRESH,
    S3_GRADE_A, S3_GRADE_B, S3_GRADE_C
)

logger = logging.getLogger("argus.autonomous")

# Conviction tickers — always scanned
CONVICTION_TICKERS = [
    s.strip().upper()
    for s in os.getenv("CONVICTION_TICKERS", "AMC,GME,IWM,SPY,NVDA").split(",")
    if s.strip()
]

SCAN_INTERVAL = int(os.getenv("ARGUS_SCAN_INTERVAL", "300"))  # 5 min default
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_ECHO", os.getenv("DISCORD_WEBHOOK_SYSTEM", ""))

# Internal URLs for subsystems
SQUEEZEOS_URL = os.getenv("SQUEEZE_OS_URL", "https://localhost:8182")
ECHOFORGE_URL = os.getenv("ECHO_FORGE_URL", "http://localhost:8001")


class AutonomousScanner:
    """
    Runs in the background, fetches subsystem data from SqueezeOS & Echo Forge,
    feeds it through the Omega Fusion Engine, and alerts Discord on high-conviction signals.
    """

    def __init__(self):
        self.is_running = False
        self.alert_history = {}  # symbol -> last_alert_time
        self.cooldown_hours = float(os.getenv("ARGUS_ALERT_COOLDOWN_HOURS", "4.0"))
        self._client = None

    def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0, verify=False)
        return self._client

    async def start_loop(self):
        """Main autonomous scanning loop."""
        self.is_running = True
        logger.info("=" * 50)
        logger.info("  ARGUS OMEGA AUTONOMOUS SCANNER — ONLINE")
        logger.info("  Tickers: %s", ", ".join(CONVICTION_TICKERS))
        logger.info("  Interval: %ds | Cooldown: %.1fh", SCAN_INTERVAL, self.cooldown_hours)
        logger.info("=" * 50)

        # Initial wait for services to stabilize
        await asyncio.sleep(10)

        await self._send_discord_alert(
            title="🛡️ Argus Omega Scanner — ONLINE",
            description=(
                f"Autonomous Fusion Scanner activated.\n"
                f"**Tickers**: {', '.join(CONVICTION_TICKERS)}\n"
                f"**Cadence**: Every {SCAN_INTERVAL // 60} min"
            ),
            color=0x2ecc71  # Green
        )

        while self.is_running:
            try:
                for ticker in CONVICTION_TICKERS:
                    if not self.is_running:
                        break
                    await self._scan_ticker(ticker)
                    # Jitter between scans
                    await asyncio.sleep(random.uniform(3, 8))

            except Exception as e:
                logger.error("Scanner loop error: %s", e)
                await asyncio.sleep(30)

            await asyncio.sleep(SCAN_INTERVAL)

    async def _scan_ticker(self, ticker: str):
        """Scan a single ticker through the fusion pipeline."""
        now = datetime.now(timezone.utc)

        # Cooldown check
        if ticker in self.alert_history:
            elapsed = now - self.alert_history[ticker]
            if elapsed < timedelta(hours=self.cooldown_hours):
                return

        try:
            # Fetch subsystem signals
            squeeze_data = await self._fetch_squeeze_signal(ticker)
            echo_data = await self._fetch_echo_signal(ticker)

            if not squeeze_data and not echo_data:
                logger.info("No subsystem data available for %s — skipping", ticker)
                return

            # Build a lightweight Omega assessment
            score, conviction, bias, assessment = self._compute_omega_lite(
                ticker, squeeze_data, echo_data
            )

            logger.info(
                "Omega Scan: %s | Score: %.0f | Conviction: %s | Bias: %s",
                ticker, score, conviction, bias
            )

            # Only alert on meaningful signals
            if score >= S3_GRADE_C and conviction != "low":
                await self._fire_omega_alert(
                    ticker, score, conviction, bias, assessment,
                    squeeze_data, echo_data
                )
                self.alert_history[ticker] = now

        except Exception as e:
            logger.error("Omega scan failed for %s: %s", ticker, e)

    async def _fetch_squeeze_signal(self, ticker: str) -> dict:
        """Fetch squeeze/flow data from SqueezeOS."""
        try:
            client = self._get_client()
            resp = await client.get(f"{SQUEEZEOS_URL}/api/beast/signals")
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    if item.get("symbol", "").upper() == ticker:
                        return item
        except Exception as e:
            logger.warning("SqueezeOS fetch failed for %s: %s", ticker, e)
        return {}

    async def _fetch_echo_signal(self, ticker: str) -> dict:
        """Fetch echo pattern data from Echo Forge."""
        try:
            client = self._get_client()
            resp = await client.post(
                f"{ECHOFORGE_URL}/echo_scan",
                json={"ticker": ticker, "timeframe": "1h", "window_size": 60, "top_n": 10}
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Echo Forge fetch failed for %s: %s", ticker, e)
        return {}

    def _compute_omega_lite(self, ticker: str, squeeze: dict, echo: dict) -> tuple:
        """
        Lightweight Omega Fusion — combines available subsystem data
        into a score/conviction/bias without requiring the full request schema.
        """
        score = 0.0
        bias = "neutral"
        factors = []

        # Squeeze component
        if squeeze:
            sq_score = squeeze.get("squeeze_score", 0)
            direction = squeeze.get("direction", "NEUTRAL").upper()
            score += sq_score * 0.50  # 50% weight to squeeze
            if direction == "BULLISH":
                bias = "bullish"
            elif direction == "BEARISH":
                bias = "bearish"
            factors.append(f"SQZ:{sq_score:.0f}")

        # Echo component
        if echo:
            confidence = echo.get("confidence", 0)
            if isinstance(confidence, str):
                confidence = float(confidence) if confidence.replace(".", "").isdigit() else 0
            echo_score = confidence * 100  # Convert 0-1 to 0-100
            score += echo_score * 0.30  # 30% weight to echo
            factors.append(f"ECHO:{echo_score:.0f}")

            # Echo bias override
            proj = echo.get("projection", {})
            if proj:
                prob_up = proj.get("prob_continuation", 0.5)
                if prob_up > 0.65 and bias != "bearish":
                    bias = "bullish"
                elif prob_up < 0.35 and bias != "bullish":
                    bias = "bearish"

        # Baseline component (always contribute minimum)
        score += 10  # Base 10 points for having data at all
        score = min(score, 100)

        # Conviction mapping
        if score >= S3_GRADE_A:
            conviction = "extreme"
        elif score >= S3_GRADE_B:
            conviction = "high"
        elif score >= S3_GRADE_C:
            conviction = "moderate"
        else:
            conviction = "low"

        assessment = " | ".join(factors) if factors else "Insufficient data"

        return score, conviction, bias, assessment

    async def _fire_omega_alert(
        self, ticker: str, score: float, conviction: str,
        bias: str, assessment: str, squeeze: dict, echo: dict
    ):
        """Send the Omega Fusion signal to Discord."""
        # Color by bias
        if bias == "bullish":
            color = 0x00FF88  # Green
            emoji = "🟢"
        elif bias == "bearish":
            color = 0xFF4444  # Red
            emoji = "🔴"
        else:
            color = 0x00BFFF  # Blue
            emoji = "📊"

        # Grade
        if score >= S3_GRADE_A:
            grade = "A"
            grade_emoji = "🔥"
        elif score >= S3_GRADE_B:
            grade = "B"
            grade_emoji = "⚡"
        elif score >= S3_GRADE_C:
            grade = "C"
            grade_emoji = "📈"
        else:
            grade = "D"
            grade_emoji = "📉"

        # Price from squeeze data
        price = squeeze.get("price", 0) if squeeze else 0
        change_pct = squeeze.get("changePct", 0) if squeeze else 0

        fields = [
            {"name": f"{grade_emoji} Grade", "value": f"**{grade}-SETUP**", "inline": True},
            {"name": "🧠 Omega Score", "value": f"**{score:.0f}**/100", "inline": True},
            {"name": "📡 Conviction", "value": f"**{conviction.upper()}**", "inline": True},
            {"name": f"{emoji} Bias", "value": f"**{bias.upper()}**", "inline": True},
        ]

        if price:
            fields.append({"name": "💰 Price", "value": f"**${price:.2f}**", "inline": True})
        if change_pct:
            fields.append({"name": "📈 Change", "value": f"**{change_pct:+.1f}%**", "inline": True})

        fields.append({"name": "🔬 Modules", "value": f"`{assessment}`", "inline": False})

        await self._send_discord_alert(
            title=f"🛡️ OMEGA FUSION: {ticker} — {bias.upper()} ({grade})",
            description=f"Institutional fusion scan complete for **{ticker}**",
            color=color,
            fields=fields
        )

    async def _send_discord_alert(
        self, title: str, description: str,
        color: int = 0x3498db, fields: list = None
    ):
        """Send an embed to the configured Discord webhook."""
        if not DISCORD_WEBHOOK:
            logger.warning("No Discord webhook configured for Argus Omega")
            return

        payload = {
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "fields": fields or [],
                "footer": {"text": f"Argus Omega • ScriptMasterLabs™ • {datetime.now().strftime('%I:%M %p ET')}"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(DISCORD_WEBHOOK, json=payload, timeout=10) as resp:
                    if resp.status in (200, 204):
                        logger.info("[DISCORD] Omega alert sent: %s (HTTP %d)", title, resp.status)
                    else:
                        logger.error("[DISCORD] Omega alert failed: HTTP %d", resp.status)
        except Exception as e:
            logger.error("[DISCORD] Omega alert error: %s", e)

    def stop(self):
        self.is_running = False
        logger.info("Autonomous Scanner Shutdown Requested.")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
