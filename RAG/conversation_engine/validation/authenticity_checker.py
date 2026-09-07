"""
AuthenticityChecker - Post-generation validation for indistinguishable responses.

Validates AI-generated responses to ensure they:
1. Contain required voiceprint elements (lexicon phrases, signature)
2. Avoid forbidden AI-sounding patterns
3. Match expected emotional tone for context
4. Use correct signature format for communication context

Can optionally auto-fix minor issues like:
- Adding missing signatures
- Removing numbered list prefixes
- Adding missing P.S. for certain executives

Usage:
    checker = AuthenticityChecker()
    result = checker.validate(
        response="...",
        voiceprint={...},
        calibration=ResponseCalibration(...)
    )

    if not result.is_valid:
        fixed = checker.fix_response(response, result.issues, voiceprint)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity of authenticity issues."""
    CRITICAL = "critical"  # Must regenerate
    WARNING = "warning"    # Can auto-fix
    INFO = "info"          # Minor, log only


@dataclass
class ValidationIssue:
    """A single validation issue found in the response."""
    category: str
    description: str
    severity: IssueSeverity
    pattern_found: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of authenticity validation."""
    is_valid: bool
    authenticity_score: float  # 0.0 to 1.0
    issues: List[ValidationIssue] = field(default_factory=list)

    # Breakdown scores
    lexicon_score: float = 1.0
    forbidden_pattern_score: float = 1.0
    signature_score: float = 1.0
    tone_score: float = 1.0

    def __post_init__(self):
        """Calculate overall authenticity score."""
        if not self.issues:
            self.authenticity_score = 1.0
        else:
            # Weight different aspects
            self.authenticity_score = (
                self.lexicon_score * 0.3 +
                self.forbidden_pattern_score * 0.4 +
                self.signature_score * 0.2 +
                self.tone_score * 0.1
            )


class AuthenticityChecker:
    """
    Post-generation validation to catch AI-sounding patterns.

    Validates:
    1. Presence of required voiceprint elements
    2. Absence of forbidden AI patterns
    3. Correct signature for context
    4. Appropriate emotional tone

    Can auto-fix minor issues when fixable=True.
    """

    # Forbidden AI patterns - these scream "AI-generated"
    FORBIDDEN_PATTERNS = [
        # Generic AI phrases
        (r"I'd be happy to", "Generic AI phrase"),
        (r"I would be happy to", "Generic AI phrase"),
        (r"I'm happy to help", "Generic AI phrase"),
        (r"Here's a breakdown", "Generic AI phrase"),
        (r"Let me break this down", "Generic AI phrase"),
        (r"Great question!", "Generic AI phrase"),
        (r"That's a great question", "Generic AI phrase"),
        (r"Absolutely!", "Generic AI phrase (at start)"),
        (r"Certainly!", "Generic AI phrase"),
        (r"Of course!", "Generic AI phrase (at start)"),

        # AI self-references
        (r"As an AI", "AI self-reference"),
        (r"I don't have personal", "AI self-reference"),
        (r"Based on my training", "AI self-reference"),
        (r"I cannot access", "AI self-reference"),
        (r"I don't have access to", "AI self-reference"),

        # Over-structured responses
        (r"^1\.\s", "Numbered list at start"),
        (r"^##\s", "Markdown header"),
        (r"^\*\*[^*]+\*\*$", "Bold-only line (markdown)"),
        (r"^-\s{2,}", "Bullet point with extra spacing"),

        # Formal/stiff language
        (r"In conclusion,", "Overly formal conclusion"),
        (r"To summarize,", "Overly formal summary"),
        (r"It's important to note that", "Filler phrase"),
        (r"It's worth noting that", "Filler phrase"),
        (r"I hope this helps", "Generic AI closing"),
        (r"Please let me know if you have any", "Generic AI closing"),
        (r"Feel free to ask", "Generic AI closing"),
    ]

    # Patterns that are OK in some contexts but suspicious
    CONTEXTUAL_PATTERNS = [
        (r"^[-•]\s", "Bullet point", ["data_heavy", "list_requested"]),
        (r"^\d+\.\s", "Numbered item", ["data_heavy", "steps_requested"]),
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Initialize AuthenticityChecker.

        Args:
            strict_mode: If True, treat warnings as errors
        """
        self.strict_mode = strict_mode
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._forbidden_compiled = [
            (re.compile(pattern, re.IGNORECASE | re.MULTILINE), desc)
            for pattern, desc in self.FORBIDDEN_PATTERNS
        ]
        self._contextual_compiled = [
            (re.compile(pattern, re.MULTILINE), desc, contexts)
            for pattern, desc, contexts in self.CONTEXTUAL_PATTERNS
        ]

    def validate(
        self,
        response: str,
        voiceprint: Optional[Dict[str, Any]] = None,
        calibration: Optional[Any] = None,
        executive_name: Optional[str] = None,
        context_flags: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Validate response for authenticity.

        Args:
            response: The AI-generated response to validate
            voiceprint: Executive's voiceprint data
            calibration: Response calibration with tone/context info
            executive_name: Executive name for signature checking
            context_flags: Context flags like ["data_heavy", "crisis"]

        Returns:
            ValidationResult with issues and scores
        """
        issues: List[ValidationIssue] = []
        context_flags = context_flags or []

        # 1. Check for forbidden patterns
        forbidden_score = self._check_forbidden_patterns(response, issues)

        # 2. Check contextual patterns
        self._check_contextual_patterns(response, context_flags, issues)

        # 3. Check for voiceprint elements
        lexicon_score = self._check_lexicon_presence(response, voiceprint, issues)

        # 4. Check signature
        signature_score = self._check_signature(
            response, voiceprint, executive_name, issues
        )

        # 5. Check emotional tone (if calibration provided)
        tone_score = self._check_tone(response, calibration, issues)

        # Calculate if valid
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        warning_issues = [i for i in issues if i.severity == IssueSeverity.WARNING]

        is_valid = len(critical_issues) == 0
        if self.strict_mode and warning_issues:
            is_valid = False

        result = ValidationResult(
            is_valid=is_valid,
            authenticity_score=0.0,  # Will be calculated in __post_init__
            issues=issues,
            lexicon_score=lexicon_score,
            forbidden_pattern_score=forbidden_score,
            signature_score=signature_score,
            tone_score=tone_score,
        )

        # Recalculate score after setting component scores
        result.authenticity_score = (
            result.lexicon_score * 0.3 +
            result.forbidden_pattern_score * 0.4 +
            result.signature_score * 0.2 +
            result.tone_score * 0.1
        )

        logger.debug(
            f"Validation complete: valid={is_valid}, score={result.authenticity_score:.2f}, "
            f"issues={len(issues)}"
        )

        return result

    def _check_forbidden_patterns(
        self,
        response: str,
        issues: List[ValidationIssue]
    ) -> float:
        """
        Check for forbidden AI patterns.

        Returns score from 0.0 (many issues) to 1.0 (no issues).
        """
        found_count = 0

        for pattern, description in self._forbidden_compiled:
            matches = pattern.findall(response)
            if matches:
                found_count += len(matches)
                # First match of each pattern is critical, rest are warnings
                severity = IssueSeverity.CRITICAL if found_count <= 2 else IssueSeverity.WARNING

                issues.append(ValidationIssue(
                    category="forbidden_pattern",
                    description=f"Found forbidden pattern: {description}",
                    severity=severity,
                    pattern_found=matches[0] if isinstance(matches[0], str) else str(matches[0]),
                    suggestion=f"Remove or rephrase: '{matches[0]}'"
                ))

                logger.debug(f"Forbidden pattern found: {description} - '{matches[0]}'")

        # Score: 1.0 for 0 patterns, decreasing with more
        if found_count == 0:
            return 1.0
        elif found_count == 1:
            return 0.7
        elif found_count == 2:
            return 0.4
        else:
            return 0.1

    def _check_contextual_patterns(
        self,
        response: str,
        context_flags: List[str],
        issues: List[ValidationIssue]
    ):
        """Check patterns that are OK in some contexts but not others."""
        for pattern, description, allowed_contexts in self._contextual_compiled:
            if pattern.search(response):
                # Check if any allowed context is present
                if not any(ctx in context_flags for ctx in allowed_contexts):
                    issues.append(ValidationIssue(
                        category="contextual_pattern",
                        description=f"Found {description} outside appropriate context",
                        severity=IssueSeverity.WARNING,
                        suggestion=f"Consider removing {description} or use flowing prose"
                    ))

    def _check_lexicon_presence(
        self,
        response: str,
        voiceprint: Optional[Dict[str, Any]],
        issues: List[ValidationIssue]
    ) -> float:
        """
        Check if voiceprint lexicon phrases are present.

        We expect at least 1-2 lexicon phrases in a typical response.
        """
        if not voiceprint:
            return 1.0  # Can't check without voiceprint

        # Get lexicon
        lexicon = voiceprint.get("lexicon", [])
        if not lexicon:
            return 1.0

        # Check for presence (case-insensitive partial match)
        response_lower = response.lower()
        matches = []

        for phrase in lexicon[:15]:  # Check top 15 phrases
            phrase_lower = phrase.lower().rstrip("...")  # Handle phrases ending in ...
            if phrase_lower in response_lower:
                matches.append(phrase)

        # Also check signature opener and sign-off
        vp = voiceprint.get("voiceprint", voiceprint)
        opener = vp.get("signature_opener", {})
        if isinstance(opener, dict):
            opener_text = opener.get("text", "").lower()
            if opener_text and opener_text.rstrip("...") in response_lower:
                matches.append(opener.get("text"))

        # Score based on matches
        if len(matches) >= 2:
            return 1.0
        elif len(matches) == 1:
            return 0.7
        else:
            issues.append(ValidationIssue(
                category="missing_lexicon",
                description="No voiceprint lexicon phrases found in response",
                severity=IssueSeverity.WARNING,
                suggestion=f"Consider including phrases like: {', '.join(lexicon[:3])}"
            ))
            return 0.4

    def _check_signature(
        self,
        response: str,
        voiceprint: Optional[Dict[str, Any]],
        executive_name: Optional[str],
        issues: List[ValidationIssue]
    ) -> float:
        """Check if response ends with appropriate signature."""
        if not voiceprint and not executive_name:
            return 1.0

        # Get expected signatures
        vp = voiceprint.get("voiceprint", voiceprint) if voiceprint else {}
        context_sigs = vp.get("context_signatures", {})

        expected_sigs = []
        if context_sigs:
            expected_sigs.extend([
                context_sigs.get("email", ""),
                context_sigs.get("slack_channel", ""),
                context_sigs.get("slack_dm", ""),
                context_sigs.get("formal", ""),
            ])

        # Add name-based signatures
        if executive_name:
            short_name = executive_name.split()[0]
            expected_sigs.extend([
                f"- {short_name}",
                f"— {short_name}",
                f"- {executive_name}",
                f"— {executive_name}",
            ])

        # Check if any signature is present near end
        last_200_chars = response[-200:] if len(response) > 200 else response

        for sig in expected_sigs:
            if sig and sig in last_200_chars:
                return 1.0

        # Check for any dash-name pattern
        if re.search(r'[-—]\s*[A-Z][a-z]+\s*$', response):
            return 0.9  # Has a signature, just not exact match

        # No signature found
        issues.append(ValidationIssue(
            category="missing_signature",
            description="Response missing executive signature",
            severity=IssueSeverity.WARNING,
            suggestion=f"Add signature like: {expected_sigs[0] if expected_sigs else '- Name'}"
        ))
        return 0.5

    def _check_tone(
        self,
        response: str,
        calibration: Optional[Any],
        issues: List[ValidationIssue]
    ) -> float:
        """Check if emotional tone matches calibration."""
        if not calibration:
            return 1.0

        # Check for crisis tone requirements
        if hasattr(calibration, 'is_crisis') and calibration.is_crisis:
            # Should NOT have emojis in crisis
            if re.search(r'[\U0001F300-\U0001F9FF]', response):
                issues.append(ValidationIssue(
                    category="tone_mismatch",
                    description="Found emojis in crisis context response",
                    severity=IssueSeverity.WARNING,
                    suggestion="Remove emojis for serious/crisis context"
                ))
                return 0.7

        # Check for celebratory requirements
        if hasattr(calibration, 'is_celebratory') and calibration.is_celebratory:
            # Should have some enthusiasm markers
            enthusiasm_markers = ["!", "great", "amazing", "proud", "excellent", "fantastic"]
            has_enthusiasm = any(m in response.lower() for m in enthusiasm_markers)
            if not has_enthusiasm:
                issues.append(ValidationIssue(
                    category="tone_mismatch",
                    description="Celebratory context but no enthusiasm in response",
                    severity=IssueSeverity.INFO,
                    suggestion="Add enthusiasm: '!', 'great work', 'I'm proud'"
                ))
                return 0.8

        return 1.0

    def fix_response(
        self,
        response: str,
        issues: List[ValidationIssue],
        voiceprint: Optional[Dict[str, Any]] = None,
        executive_name: Optional[str] = None,
    ) -> Tuple[str, List[str]]:
        """
        Attempt to fix minor issues in the response.

        Only fixes WARNING-level issues. CRITICAL issues require regeneration.

        Args:
            response: Original response
            issues: List of validation issues
            voiceprint: Executive's voiceprint
            executive_name: Executive name for signature

        Returns:
            Tuple of (fixed_response, list_of_fixes_applied)
        """
        fixed = response
        fixes_applied = []

        for issue in issues:
            if issue.severity != IssueSeverity.WARNING:
                continue

            if issue.category == "forbidden_pattern" and issue.pattern_found:
                # Remove common AI phrases
                original = fixed

                # Generic phrase removals
                if "I'd be happy to" in issue.pattern_found:
                    fixed = re.sub(r"I'd be happy to\s*", "", fixed, flags=re.IGNORECASE)
                elif "Great question" in issue.pattern_found:
                    fixed = re.sub(r"(That's a )?[Gg]reat question!?\s*", "", fixed)
                elif "Here's a breakdown" in issue.pattern_found:
                    fixed = re.sub(r"Here's a breakdown[:\s]*", "", fixed, flags=re.IGNORECASE)
                elif "Let me break this down" in issue.pattern_found:
                    fixed = re.sub(r"Let me break this down[:\s]*", "", fixed, flags=re.IGNORECASE)

                if fixed != original:
                    fixes_applied.append(f"Removed: '{issue.pattern_found}'")

            elif issue.category == "missing_signature":
                # Add signature at end
                vp = voiceprint.get("voiceprint", voiceprint) if voiceprint else {}
                context_sigs = vp.get("context_signatures", {})

                sig = context_sigs.get("email", "")
                if not sig and executive_name:
                    sig = f"- {executive_name.split()[0]}"

                if sig and sig not in fixed:
                    fixed = fixed.rstrip() + f"\n\n{sig}"
                    fixes_applied.append(f"Added signature: '{sig}'")

            elif issue.category == "contextual_pattern":
                # Remove leading list markers if not appropriate
                if "Bullet point" in issue.description:
                    # Replace bullet lines with flowing text
                    fixed = re.sub(r'^[-•]\s+', '', fixed, flags=re.MULTILINE)
                    fixes_applied.append("Removed bullet point markers")
                elif "Numbered item" in issue.description:
                    # Remove numbered list markers at line start
                    fixed = re.sub(r'^\d+\.\s+', '', fixed, flags=re.MULTILINE)
                    fixes_applied.append("Removed numbered list markers")

        # Clean up any double newlines from removals
        fixed = re.sub(r'\n{3,}', '\n\n', fixed)
        fixed = fixed.strip()

        if fixes_applied:
            logger.info(f"Applied {len(fixes_applied)} fixes to response")

        return fixed, fixes_applied

    def get_regeneration_guidance(
        self,
        issues: List[ValidationIssue]
    ) -> str:
        """
        Generate guidance for LLM regeneration based on issues.

        Used when issues are too severe to auto-fix.
        """
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]

        if not critical_issues:
            return ""

        guidance_parts = [
            "CRITICAL: Your previous response contained AI-sounding patterns.",
            "Please regenerate avoiding:",
        ]

        for issue in critical_issues[:3]:  # Top 3 issues
            guidance_parts.append(f"- {issue.description}")
            if issue.suggestion:
                guidance_parts.append(f"  Instead: {issue.suggestion}")

        guidance_parts.append("")
        guidance_parts.append("Write like a REAL executive, not like an AI assistant.")

        return "\n".join(guidance_parts)


# Convenience function for quick validation
def validate_response(
    response: str,
    voiceprint: Optional[Dict[str, Any]] = None,
    executive_name: Optional[str] = None,
) -> ValidationResult:
    """
    Quick validation of a response.

    Usage:
        result = validate_response(response, voiceprint)
        if not result.is_valid:
            print(f"Issues: {result.issues}")
    """
    checker = AuthenticityChecker()
    return checker.validate(
        response=response,
        voiceprint=voiceprint,
        executive_name=executive_name,
    )
