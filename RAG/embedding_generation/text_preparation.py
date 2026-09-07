"""
Text preparation module for embedding generation.
Formats database records into structured, embedding-ready text.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def prepare_executive_profile_text(profile_record: Dict[str, Any]) -> str:
    """
    Extract and format executive profile for embedding.
    
    Args:
        profile_record: Row from executive_profiles table
            Must include: id, name, title, department, profile_data (JSONB)
    
    Returns:
        Formatted string ready for embedding
        
    Raises:
        ValueError: If required fields are missing
    """
    try:
        # Extract basic fields
        name = profile_record.get('name', 'Unknown')
        title = profile_record.get('title', 'Unknown')
        department = profile_record.get('department', 'Unknown')
        
        # Parse profile_data (JSONB field)
        if isinstance(profile_record.get('profile_data'), str):
            profile_data = json.loads(profile_record['profile_data'])
        else:
            profile_data = profile_record.get('profile_data', {})
        
        # Extract and flatten background data
        background_data = profile_data.get('background', {})
        if isinstance(background_data, dict):
            background_parts = []

            # Education
            if 'education' in background_data:
                background_parts.append(f"Education: {background_data['education']}")

            # Previous roles
            if 'previous_roles' in background_data:
                roles = background_data['previous_roles']
                if isinstance(roles, list):
                    background_parts.append("Previous Roles:")
                    for role in roles:
                        background_parts.append(f"  - {role}")

            # Expertise
            if 'expertise' in background_data:
                expertise = background_data['expertise']
                if isinstance(expertise, list):
                    background_parts.append(f"Expertise: {', '.join(expertise)}")

            # Company info
            if 'company_info' in background_data:
                company = background_data['company_info']
                if isinstance(company, dict):
                    background_parts.append("Company Information:")
                    if 'name' in company:
                        background_parts.append(f"  Company Name: {company['name']}")
                    if 'founded' in company:
                        background_parts.append(f"  Founded: {company['founded']}")
                    if 'employees' in company:
                        background_parts.append(f"  Employees: {company['employees']}")
                    if 'parent_company' in company:
                        background_parts.append(f"  Parent Company: {company['parent_company']}")
                    if 'mission' in company:
                        background_parts.append(f"  Mission: {company['mission']}")
                    if 'location' in company:
                        background_parts.append(f"  Location: {company['location']}")
                    if 'capital' in company:
                        background_parts.append(f"  Capital: {company['capital']}")

            # Leadership team
            if 'leadership_team' in background_data:
                team = background_data['leadership_team']
                if isinstance(team, list) and team:
                    background_parts.append("Leadership Team:")
                    for member in team:
                        if isinstance(member, dict):
                            member_name = member.get('name', 'Unknown')
                            member_title = member.get('title', '')
                            member_bg = member.get('background', '')
                            background_parts.append(f"  - {member_name} ({member_title}): {member_bg}")

            background = '\n'.join(background_parts) if background_parts else 'No background information available'
        elif isinstance(background_data, str):
            background = background_data
        else:
            background = 'No background information available'
        
        # Communication style
        comm_style = profile_data.get('communication_style', {})
        formality = comm_style.get('formality_scale', 'N/A')
        directness = comm_style.get('directness_scale', 'N/A')
        warmth = comm_style.get('warmth_scale', 'N/A')
        phrases = comm_style.get('common_phrases', [])
        phrases_str = ', '.join(phrases) if phrases else 'None documented'
        
        # Core values
        core_values = profile_data.get('core_values', [])
        if core_values:
            values_list = []
            for i, value in enumerate(core_values, 1):
                if isinstance(value, dict):
                    value_name = value.get('value', 'Unknown')
                    priority = value.get('priority', 'N/A')
                    description = value.get('description', '')
                    values_list.append(f"{i}. {value_name} (Priority: {priority}): {description}")
                else:
                    values_list.append(f"{i}. {value}")
            values_str = '\n'.join(values_list)
        else:
            values_str = 'No core values documented'
        
        # Decision making approach
        decision_making = profile_data.get('decision_making_approach', {})
        decision_speed = decision_making.get('decision_speed', 'Unknown')
        risk_tolerance = decision_making.get('risk_tolerance', 'Unknown')
        decision_style = decision_making.get('decision_style', 'Unknown')
        
        # Construct formatted text
        embedding_text = f"""Executive Profile: {name}
Title: {title}
Department: {department}

Background:
{background}

Communication Style:
Formality: {formality}/10
Directness: {directness}/10
Warmth: {warmth}/10
Common phrases: {phrases_str}

Core Values:
{values_str}

Decision Making Approach:
Speed: {decision_speed}
Risk Tolerance: {risk_tolerance}
Style: {decision_style}
"""
        
        logger.debug(f"Prepared executive profile text for {name} ({len(embedding_text)} chars)")
        return embedding_text.strip()
        
    except Exception as e:
        logger.error(f"Error preparing executive profile text: {e}")
        logger.error(f"Record data: {profile_record}")
        raise ValueError(f"Failed to prepare executive profile text: {e}")


def prepare_decision_case_text(decision_record: Dict[str, Any]) -> str:
    """
    Format decision case for embedding.
    
    Args:
        decision_record: Row from decision_cases table
            Must include: id, title, situation, decision_made, rationale, etc.
    
    Returns:
        Formatted string ready for embedding
        
    Raises:
        ValueError: If required fields are missing
    """
    try:
        # Extract fields from decision record
        decision_id = decision_record.get('id', 'Unknown')
        title = decision_record.get('title', 'Untitled Decision')
        executive_id = decision_record.get('executive_id', 'Unknown')
        category = decision_record.get('category', 'Unknown')
        date = decision_record.get('date', 'Unknown date')
        
        situation = decision_record.get('situation', 'No situation description')
        decision_made = decision_record.get('decision_made', 'No decision documented')
        rationale = decision_record.get('rationale', 'No rationale provided')
        outcome = decision_record.get('outcome', 'Outcome not yet documented')
        lessons_learned = decision_record.get('lessons_learned', 'No lessons learned documented')
        
        confidence = decision_record.get('confidence', 'N/A')
        precedent = decision_record.get('precedent', False)
        precedent_str = 'Yes' if precedent else 'No'
        
        # Construct formatted text
        embedding_text = f"""Decision Case: {title}
Decision ID: {decision_id}
Executive: {executive_id}
Category: {category}
Date: {date}

Situation:
{situation}

Decision Made:
{decision_made}

Rationale:
{rationale}

Outcome:
{outcome}

Lessons Learned:
{lessons_learned}

Confidence: {confidence}
Precedent: {precedent_str}
"""
        
        logger.debug(f"Prepared decision case text for {decision_id} ({len(embedding_text)} chars)")
        return embedding_text.strip()
        
    except Exception as e:
        logger.error(f"Error preparing decision case text: {e}")
        logger.error(f"Record data: {decision_record}")
        raise ValueError(f"Failed to prepare decision case text: {e}")


def prepare_policy_text(policy_record: Dict[str, Any], max_length: int = 8000) -> str:
    """
    Format policy document for embedding.
    
    Args:
        policy_record: Row from policy_documents table
            Must include: id, name, version, content_markdown
        max_length: Maximum characters for content (truncate if longer)
    
    Returns:
        Formatted string ready for embedding
        
    Raises:
        ValueError: If required fields are missing
    """
    try:
        # Extract fields
        policy_id = policy_record.get('id', 'Unknown')
        name = policy_record.get('name', 'Untitled Policy')
        version = policy_record.get('version', 'N/A')
        content = policy_record.get('content_markdown', 'No content available')
        
        # Truncate content if too long
        if len(content) > max_length:
            logger.warning(f"Policy {policy_id} content truncated from {len(content)} to {max_length} chars")
            content = content[:max_length] + "\n\n[Content truncated due to length...]"
        
        # Construct formatted text
        embedding_text = f"""Policy: {name}
Version: {version}
ID: {policy_id}

Content:
{content}
"""
        
        logger.debug(f"Prepared policy text for {policy_id} ({len(embedding_text)} chars)")
        return embedding_text.strip()
        
    except Exception as e:
        logger.error(f"Error preparing policy text: {e}")
        logger.error(f"Record data: {policy_record}")
        raise ValueError(f"Failed to prepare policy text: {e}")


def prepare_document_section_text(section_record: Dict[str, Any]) -> str:
    """
    Format document section for embedding.

    Args:
        section_record: Row from document_sections table
            Must include: id, section_title, content, parent_document_type

    Returns:
        Formatted string ready for embedding

    Raises:
        ValueError: If required fields are missing
    """
    try:
        section_id = section_record.get('id', 'Unknown')
        title = section_record.get('section_title', 'Untitled Section')
        content = section_record.get('content', '')
        parent_type = section_record.get('parent_document_type', 'unknown')
        parent_id = section_record.get('parent_document_id', 'unknown')
        section_type = section_record.get('section_type', '')

        embedding_text = f"""Document Section: {title}
Section ID: {section_id}
Parent Document: {parent_id} ({parent_type})
Section Type: {section_type}

Content:
{content}
"""
        logger.debug(f"Prepared document section text for {section_id} ({len(embedding_text)} chars)")
        return embedding_text.strip()

    except Exception as e:
        logger.error(f"Error preparing document section text: {e}")
        raise ValueError(f"Failed to prepare document section text: {e}")


def validate_text(text: str, min_length: int = 10) -> bool:
    """
    Validate that prepared text is suitable for embedding.
    
    Args:
        text: The prepared text
        min_length: Minimum acceptable length
    
    Returns:
        True if valid, False otherwise
    """
    if not text or not isinstance(text, str):
        logger.warning("Text is empty or not a string")
        return False
    
    if len(text.strip()) < min_length:
        logger.warning(f"Text too short ({len(text)} chars, min {min_length})")
        return False
    
    # Check for valid UTF-8
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        logger.warning("Text contains invalid UTF-8 characters")
        return False
    
    return True


# Example usage and testing
if __name__ == "__main__":
    # Test with sample data
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing text preparation functions...")
    
    # Test executive profile
    sample_profile = {
        'id': 'exec_001_test',
        'name': 'Akiko Tanaka',
        'title': 'CEO',
        'department': 'Executive',
        'profile_data': {
            'background': 'Seasoned executive with 20 years experience',
            'communication_style': {
                'formality_scale': 8,
                'directness_scale': 7,
                'warmth_scale': 6,
                'common_phrases': ['Let me think about this', 'Walk me through...']
            },
            'core_values': [
                {'value': 'Customer First', 'priority': 'High', 'description': 'Always prioritize customer needs'}
            ],
            'decision_making_approach': {
                'decision_speed': 'Moderate',
                'risk_tolerance': 'Balanced',
                'decision_style': 'Analytical'
            }
        }
    }
    
    profile_text = prepare_executive_profile_text(sample_profile)
    print("\n" + "="*60)
    print("EXECUTIVE PROFILE TEXT:")
    print("="*60)
    print(profile_text)
    print(f"\nValid: {validate_text(profile_text)}")
    
    # Test decision case
    sample_decision = {
        'id': 'exec_001_test_DEC_001',
        'title': 'MegaCorp Discount Approval',
        'executive_id': 'exec_001_test',
        'category': 'Pricing',
        'date': '2024-01-22',
        'situation': 'Customer requested 20% discount',
        'decision_made': 'Approved 15% with value-adds',
        'rationale': 'Maintain pricing integrity while keeping strategic customer',
        'outcome': 'Customer signed 3-year contract',
        'lessons_learned': 'Value-adds are powerful negotiation tools',
        'confidence': '90%',
        'precedent': True
    }
    
    decision_text = prepare_decision_case_text(sample_decision)
    print("\n" + "="*60)
    print("DECISION CASE TEXT:")
    print("="*60)
    print(decision_text)
    print(f"\nValid: {validate_text(decision_text)}")
    
    print("\n✅ Text preparation tests completed!")
