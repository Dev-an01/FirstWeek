"""
Speaking Style Section Builder - Natural speech patterns for audio/video mode.

Uses speaking_patterns_video from voiceprint to inject natural verbal patterns.
Only included for audio endpoints (stream-audio-natural).

Target: 80-100 tokens
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpeakingStyleSection:
    """
    Builds speaking style section for natural vocal delivery.

    Reads patterns from voiceprint.speaking_patterns_video and creates
    language-appropriate guidance for the LLM.

    Output format (Japanese):
        SPEAKING STYLE (自然な話し方):
        あなたは話しています、書いていません。

        フィラー: あの、ま、まあ、なんか
        強調: むちゃくちゃ、本当に
        文末: ですね、と思います
        ...

    Output format (English - lighter):
        SPEAKING STYLE (natural speech):
        You are speaking aloud, not writing.

        Fillers: "you know", "actually", "so"
        ...

    Target: 80-100 tokens
    """

    def build(
        self,
        voiceprint: Optional[Dict[str, Any]],
        language: str = "ja",
        max_tokens: int = 90,
    ) -> str:
        """
        Build speaking style section from voiceprint.

        Args:
            voiceprint: Executive voiceprint with speaking_patterns_video
            language: Response language (ja/en)
            max_tokens: Maximum tokens for section

        Returns:
            Speaking style section string
        """
        if not voiceprint:
            logger.debug("No voiceprint provided, skipping speaking style section")
            return ""

        patterns = voiceprint.get("speaking_patterns_video", {})
        if not patterns:
            logger.debug("No speaking_patterns_video in voiceprint, skipping")
            return ""

        # Build language-appropriate guidance
        if language == "ja":
            section = self._build_japanese_style(patterns)
        else:
            section = self._build_english_style(patterns)

        logger.debug(f"Built speaking style section for lang={language}: {len(section)} chars")
        return section

    def _build_japanese_style(self, patterns: Dict[str, Any]) -> str:
        """Build Japanese speaking style guidance (heavy patterns)."""
        lines: List[str] = []

        # Header
        lines.append("SPEAKING STYLE (自然な話し方):")
        lines.append("あなたは話しています、書いていません。自然な口語パターンを使ってください。")
        lines.append("")

        # Fillers
        fillers = patterns.get("verbal_fillers", {})
        if fillers_ja := fillers.get("patterns_ja", []):
            lines.append(f"フィラー（自然に、毎文ではなく）: {', '.join(fillers_ja)}")

        # Connectors
        connectors = patterns.get("connectors", {})
        if connectors_ja := connectors.get("patterns_ja", []):
            lines.append(f"接続表現: {', '.join(connectors_ja[:3])}")

        # Intensifiers
        intensifiers = patterns.get("intensifiers", {})
        if intensifiers_ja := intensifiers.get("patterns_ja", []):
            lines.append(f"強調（控えめに）: {', '.join(intensifiers_ja[:3])}")

        # Sentence endings
        endings = patterns.get("sentence_endings", {})
        if endings_ja := endings.get("patterns_ja", []):
            lines.append(f"文末パターン: {', '.join(endings_ja[:4])}")

        # Enthusiasm
        enthusiasm = patterns.get("enthusiasm", {})
        if enthusiasm_ja := enthusiasm.get("patterns_ja", []):
            lines.append(f"熱意を示す: {', '.join(enthusiasm_ja[:3])}")

        # Humility
        humility = patterns.get("humility", {})
        if humility_ja := humility.get("patterns_ja", []):
            lines.append(f"謙虚さ: {', '.join(humility_ja[:2])}")

        # Delivery guidance
        lines.append("")
        lines.append("配信スタイル:")
        lines.append("- 会話調で、フォーマルではなく")
        lines.append("- 時々自己修正を入れる（自然に聞こえる）")
        lines.append("- ワクワクで興奮を示す")

        return "\n".join(lines)

    def _build_english_style(self, patterns: Dict[str, Any]) -> str:
        """Build English speaking style guidance (lighter patterns)."""
        lines: List[str] = []

        # Header
        lines.append("SPEAKING STYLE (natural speech):")
        lines.append("You are speaking aloud, not writing. Use conversational patterns.")
        lines.append("")

        # Fillers
        fillers = patterns.get("verbal_fillers", {})
        if fillers_en := fillers.get("patterns_en", []):
            quoted = [f'"{f}"' for f in fillers_en[:3]]
            lines.append(f"Fillers (use naturally): {', '.join(quoted)}")

        # Intensifiers
        intensifiers = patterns.get("intensifiers", {})
        if intensifiers_en := intensifiers.get("patterns_en", []):
            quoted = [f'"{i}"' for i in intensifiers_en[:3]]
            lines.append(f"Emphasis: {', '.join(quoted)}")

        # Enthusiasm
        enthusiasm = patterns.get("enthusiasm", {})
        if enthusiasm_en := enthusiasm.get("patterns_en", []):
            quoted = [f'"{e}"' for e in enthusiasm_en[:3]]
            lines.append(f"Enthusiasm: {', '.join(quoted)}")

        # Delivery guidance
        lines.append("")
        lines.append("Delivery:")
        lines.append("- Speak conversationally, not formally")
        lines.append("- Occasional self-corrections are natural")
        lines.append("- Show genuine enthusiasm when excited")

        return "\n".join(lines)
