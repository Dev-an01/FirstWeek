"""
Relationship Adapter - Layer 5 of the Cognitive Twin system.

Adapts communication based on WHO is asking. An executive speaks differently
to their CEO, their team members, or their peers.

Key principle: Communication style varies by relationship. Sarah (CMO) talks to
the CEO with strategic framing, to the CFO with metrics focus, and to her team
with collaborative energy.

This layer detects the user's role and adapts the response accordingly.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List

from .config import is_layer_enabled, get_layer_config
from .profile_loader import get_cognitive_profile_loader, CommunicationStyle

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """Classification of user roles."""
    CEO = "ceo"
    CFO = "cfo"
    CTO = "cto"
    CMO = "cmo"
    COO = "coo"
    VP = "vp"
    DIRECTOR = "director"
    MANAGER = "manager"
    IC = "individual_contributor"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class RelationshipType(Enum):
    """Type of relationship between executive and user."""
    REPORT_TO = "report_to"      # Executive reports to user (user is boss)
    PEER = "peer"                # Same level
    MANAGES = "manages"          # Executive manages user (user is report)
    CROSS_FUNCTIONAL = "cross_functional"  # Different department
    EXTERNAL = "external"        # External stakeholder
    UNKNOWN = "unknown"


@dataclass
class RelationshipContext:
    """Context about the relationship between executive and user."""
    user_role: UserRole
    relationship_type: RelationshipType

    # Communication style adaptations
    formality_adjustment: int = 0  # -3 to +3 adjustment to base formality
    depth_preference: str = "standard"  # brief, standard, comprehensive
    emphasis: List[str] = field(default_factory=list)  # What to emphasize

    # Specific adaptations
    should_use_metrics: bool = False
    should_use_strategic_framing: bool = False
    should_be_collaborative: bool = False
    should_be_directive: bool = False

    # Suggested opener
    suggested_opener: str = ""

    # Reasoning
    reasoning: str = ""


# Relationship dynamics matrix
# How each executive (by title) should communicate with different roles
RELATIONSHIP_DYNAMICS = {
    "ceo": {
        "cfo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["financial_impact", "risk", "roi"],
            "should_use_metrics": True,
            "opener": "Looking at this from the financial angle...",
        },
        "cto": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["technical_feasibility", "scalability", "timeline"],
            "should_use_metrics": False,
            "opener": "From a technical perspective...",
        },
        "cmo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["customer_impact", "brand", "market_position"],
            "should_use_metrics": True,
            "opener": "Thinking about customer impact...",
        },
        "vp": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -1,
            "emphasis": ["execution", "alignment", "support"],
            "should_be_directive": True,
            "opener": "Here's what I'm thinking...",
        },
        "director": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -1,
            "emphasis": ["execution", "goals", "resources"],
            "should_be_directive": True,
            "opener": "Let me share my perspective...",
        },
        "external": {
            "relationship_type": RelationshipType.EXTERNAL,
            "formality_adjustment": 2,
            "emphasis": ["value_proposition", "partnership", "vision"],
            "should_use_strategic_framing": True,
            "opener": "Thank you for reaching out...",
        },
    },
    "cfo": {
        "ceo": {
            "relationship_type": RelationshipType.REPORT_TO,
            "formality_adjustment": 1,
            "emphasis": ["bottom_line", "risk", "recommendation"],
            "should_use_metrics": True,
            "opener": "Here's the financial picture...",
        },
        "cto": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["budget", "roi", "efficiency"],
            "should_use_metrics": True,
            "opener": "From a cost perspective...",
        },
        "cmo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["cac", "ltv", "roi", "budget"],
            "should_use_metrics": True,
            "opener": "Looking at the unit economics...",
        },
        "manager": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -1,
            "emphasis": ["accuracy", "process", "timeline"],
            "should_be_directive": True,
            "opener": "Here's what I need...",
        },
    },
    "cto": {
        "ceo": {
            "relationship_type": RelationshipType.REPORT_TO,
            "formality_adjustment": 1,
            "emphasis": ["business_impact", "timeline", "risk"],
            "should_use_strategic_framing": True,
            "opener": "From a technical standpoint...",
        },
        "cfo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["cost", "efficiency", "investment"],
            "should_use_metrics": True,
            "opener": "Here's the technical cost-benefit...",
        },
        "cmo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["feasibility", "timeline", "integration"],
            "opener": "Technically speaking...",
        },
        "manager": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -2,
            "emphasis": ["technical_details", "approach", "blockers"],
            "should_be_collaborative": True,
            "opener": "Let's think through this...",
        },
        "ic": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -2,
            "emphasis": ["technical_approach", "learning", "growth"],
            "should_be_collaborative": True,
            "opener": "Here's how I'd approach this...",
        },
    },
    "cmo": {
        "ceo": {
            "relationship_type": RelationshipType.REPORT_TO,
            "formality_adjustment": 1,
            "emphasis": ["customer_impact", "growth", "brand"],
            "should_use_strategic_framing": True,
            "opener": "Here's the customer story...",
        },
        "cfo": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["roi", "cac", "efficiency"],
            "should_use_metrics": True,
            "opener": "Let me break down the numbers...",
        },
        "cto": {
            "relationship_type": RelationshipType.PEER,
            "formality_adjustment": 0,
            "emphasis": ["requirements", "timeline", "user_experience"],
            "opener": "From a customer experience perspective...",
        },
        "manager": {
            "relationship_type": RelationshipType.MANAGES,
            "formality_adjustment": -1,
            "emphasis": ["execution", "creativity", "metrics"],
            "should_be_collaborative": True,
            "opener": "Let's think through this together...",
        },
    },
}


class RelationshipAdapter:
    """
    Adapts communication based on the relationship between executive and user.

    Uses the relationship dynamics matrix to determine:
    - How formal to be
    - What to emphasize
    - Whether to use metrics, strategic framing, etc.
    - Suggested openers
    """

    def __init__(self):
        """Initialize the RelationshipAdapter."""
        self._profile_loader = get_cognitive_profile_loader()
        self._config = get_layer_config("enhancement.relationship_dynamics")

        logger.info("RelationshipAdapter initialized")

    def adapt(
        self,
        executive_profile_id: str,
        user_id: Optional[str] = None,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> RelationshipContext:
        """
        Get relationship context for communication adaptation.

        Args:
            executive_profile_id: Executive profile ID
            user_id: Optional user identifier
            user_metadata: Optional user metadata (role, title, department)

        Returns:
            RelationshipContext with adaptation guidance
        """
        # Check if adapter is enabled
        if not is_layer_enabled("enhancement.relationship_dynamics"):
            return RelationshipContext(
                user_role=UserRole.UNKNOWN,
                relationship_type=RelationshipType.UNKNOWN,
                reasoning="Relationship adapter disabled",
            )

        # Detect user role
        user_role = self._detect_user_role(user_metadata)

        # Get executive's title for relationship mapping
        profile = self._profile_loader.load_profile(executive_profile_id)
        if not profile:
            return RelationshipContext(
                user_role=user_role,
                relationship_type=RelationshipType.UNKNOWN,
                reasoning=f"Profile not found: {executive_profile_id}",
            )

        executive_title = self._normalize_title(profile.title)

        # Look up relationship dynamics
        dynamics = self._get_dynamics(executive_title, user_role)

        # Build relationship context
        context = RelationshipContext(
            user_role=user_role,
            relationship_type=dynamics.get(
                "relationship_type", RelationshipType.UNKNOWN
            ),
            formality_adjustment=dynamics.get("formality_adjustment", 0),
            depth_preference=dynamics.get("depth_preference", "standard"),
            emphasis=dynamics.get("emphasis", []),
            should_use_metrics=dynamics.get("should_use_metrics", False),
            should_use_strategic_framing=dynamics.get(
                "should_use_strategic_framing", False
            ),
            should_be_collaborative=dynamics.get("should_be_collaborative", False),
            should_be_directive=dynamics.get("should_be_directive", False),
            suggested_opener=dynamics.get("opener", ""),
            reasoning=f"{executive_title} -> {user_role.value}",
        )

        logger.info(
            f"RelationshipAdapter: {executive_profile_id} -> {user_role.value}, "
            f"type={context.relationship_type.value}"
        )

        return context

    def _detect_user_role(self, user_metadata: Optional[Dict[str, Any]]) -> UserRole:
        """Detect user role from metadata."""
        if not user_metadata:
            return UserRole.UNKNOWN

        # Check explicit role
        role = user_metadata.get("role", "").lower()
        title = user_metadata.get("title", "").lower()

        # Check for C-level
        if any(x in role or x in title for x in ["ceo", "chief executive"]):
            return UserRole.CEO
        if any(x in role or x in title for x in ["cfo", "chief financial"]):
            return UserRole.CFO
        if any(x in role or x in title for x in ["cto", "chief technical", "chief technology"]):
            return UserRole.CTO
        if any(x in role or x in title for x in ["cmo", "chief marketing"]):
            return UserRole.CMO
        if any(x in role or x in title for x in ["coo", "chief operating"]):
            return UserRole.COO

        # Check for VP
        if any(x in role or x in title for x in ["vp", "vice president"]):
            return UserRole.VP

        # Check for Director
        if "director" in role or "director" in title:
            return UserRole.DIRECTOR

        # Check for Manager
        if "manager" in role or "manager" in title:
            return UserRole.MANAGER

        # Check for external
        if user_metadata.get("is_external", False):
            return UserRole.EXTERNAL

        # Default to IC for internal
        if user_metadata.get("is_internal", True):
            return UserRole.IC

        return UserRole.UNKNOWN

    def _normalize_title(self, title: str) -> str:
        """Normalize executive title to match dynamics keys."""
        title_lower = title.lower()

        if any(x in title_lower for x in ["ceo", "chief executive"]):
            return "ceo"
        if any(x in title_lower for x in ["cfo", "chief financial"]):
            return "cfo"
        if any(x in title_lower for x in ["cto", "chief technical", "chief technology"]):
            return "cto"
        if any(x in title_lower for x in ["cmo", "chief marketing"]):
            return "cmo"
        if any(x in title_lower for x in ["coo", "chief operating"]):
            return "coo"

        return "unknown"

    def _get_dynamics(
        self,
        executive_title: str,
        user_role: UserRole,
    ) -> Dict[str, Any]:
        """Get relationship dynamics for executive-user pair."""
        exec_dynamics = RELATIONSHIP_DYNAMICS.get(executive_title, {})
        role_dynamics = exec_dynamics.get(user_role.value, {})

        if role_dynamics:
            return role_dynamics

        # Fallback defaults based on relationship type inference
        if user_role in [UserRole.CEO]:
            return {
                "relationship_type": RelationshipType.REPORT_TO,
                "formality_adjustment": 1,
                "emphasis": ["key_points", "recommendation"],
                "should_use_strategic_framing": True,
            }
        elif user_role in [UserRole.CFO, UserRole.CTO, UserRole.CMO, UserRole.COO]:
            return {
                "relationship_type": RelationshipType.PEER,
                "formality_adjustment": 0,
                "emphasis": ["collaboration", "alignment"],
            }
        elif user_role in [UserRole.VP, UserRole.DIRECTOR]:
            return {
                "relationship_type": RelationshipType.MANAGES,
                "formality_adjustment": -1,
                "emphasis": ["execution", "support"],
                "should_be_collaborative": True,
            }
        elif user_role in [UserRole.MANAGER, UserRole.IC]:
            return {
                "relationship_type": RelationshipType.MANAGES,
                "formality_adjustment": -2,
                "emphasis": ["guidance", "growth"],
                "should_be_collaborative": True,
            }
        elif user_role == UserRole.EXTERNAL:
            return {
                "relationship_type": RelationshipType.EXTERNAL,
                "formality_adjustment": 2,
                "emphasis": ["professionalism", "value"],
            }

        return {}

    def get_adjusted_communication_style(
        self,
        executive_profile_id: str,
        relationship_context: RelationshipContext,
    ) -> CommunicationStyle:
        """
        Get communication style adjusted for relationship.

        Takes the executive's base communication style and adjusts it
        based on the relationship context.
        """
        base_style = self._profile_loader.get_communication_style(executive_profile_id)
        if not base_style:
            return CommunicationStyle()

        # Apply formality adjustment
        adjusted_formality = max(1, min(10,
            base_style.formality_scale + relationship_context.formality_adjustment
        ))

        # Adjust warmth based on relationship type
        warmth_adjustment = 0
        if relationship_context.relationship_type == RelationshipType.MANAGES:
            warmth_adjustment = 1  # Warmer with reports
        elif relationship_context.relationship_type == RelationshipType.EXTERNAL:
            warmth_adjustment = -1  # More professional with externals

        adjusted_warmth = max(1, min(10,
            base_style.warmth_scale + warmth_adjustment
        ))

        return CommunicationStyle(
            formality_scale=adjusted_formality,
            directness_scale=base_style.directness_scale,
            warmth_scale=adjusted_warmth,
            emoji_usage=base_style.emoji_usage,
            preferred_emojis=base_style.preferred_emojis,
        )


# Singleton instance
_adapter: Optional[RelationshipAdapter] = None


def get_relationship_adapter() -> RelationshipAdapter:
    """Get the singleton RelationshipAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = RelationshipAdapter()
    return _adapter
