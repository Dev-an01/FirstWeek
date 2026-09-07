"""
RBAC Filter

Role-based access control for search results.
Filters results based on user roles and content scope.
"""

from typing import List, Dict, Any, Optional
import logging

from shared.rbac import ROLE_SCOPES, DEFAULT_ROLE, get_allowed_scopes as _shared_get_allowed_scopes

# Build RBAC_ROLES dict from shared module for backward compatibility
RBAC_ROLES = {
    role: {"allowed_scopes": scopes, "description": f"Access: {', '.join(scopes)}"}
    for role, scopes in ROLE_SCOPES.items()
}

logger = logging.getLogger('vector_search.rbac_filter')


class RBACFilter:
    """
    Filters search results based on user roles.

    RBAC scope hierarchy:
    - admin/super_admin/company_admin: All scopes (public, internal, executive, confidential)
    - executive: Executive-level and below (public, internal, executive)
    - employee: Internal and below (public, internal)
    - guest: Public only

    Scope determination priority:
    1. Explicit access_level column from embeddings table (set at upload time)
    2. access_level in JSONB metadata (fallback for metadata-only storage)
    3. Heuristic inference from source_type (legacy safety net)

    SQL-level filtering via allowed_scopes is applied in postgres_client.vector_search()
    as the primary enforcement gate. This filter acts as defense-in-depth.
    """
    
    def __init__(self):
        """Initialize RBAC filter."""
        self.roles = RBAC_ROLES
        self.default_role = DEFAULT_ROLE
        logger.info("RBACFilter initialized")
    
    def filter_results(
        self,
        results: List[Dict[str, Any]],
        role: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Filter results based on user role.
        
        Args:
            results: Search results with metadata
            role: User role (admin, executive, employee, guest)
        
        Returns:
            Filtered results list
        """
        role = role or self.default_role
        
        # Validate role
        if role not in self.roles:
            logger.warning(f"Invalid role '{role}', using default '{self.default_role}'")
            role = self.default_role
        
        # Get allowed scopes for this role
        allowed_scopes = self.roles[role]['allowed_scopes']
        
        # Filter results
        filtered = []
        for result in results:
            # Infer scope from source type and metadata
            scope = self._infer_scope(result)
            
            if scope in allowed_scopes:
                filtered.append(result)
            else:
                logger.debug(f"Filtered out {result.get('source_id')} "
                           f"(scope={scope}, role={role})")
        
        logger.debug(f"RBAC filtered: {len(results)} → {len(filtered)} results (role={role})")
        return filtered
    
    def _infer_scope(self, result: Dict[str, Any]) -> str:
        """
        Infer access scope from result metadata.

        Priority:
        1. Explicit access_level field (set during upload)
        2. Metadata access_level (in JSONB metadata)
        3. Heuristic fallback based on source_type

        Args:
            result: Search result with metadata

        Returns:
            Inferred scope (public, internal, executive, confidential)
        """
        # Priority 1: Explicit access_level column
        if result.get('access_level') in ('public', 'internal', 'executive', 'confidential'):
            return result['access_level']

        source_type = result.get('source_type')
        metadata = result.get('metadata', {})

        # Priority 2: access_level in JSONB metadata
        meta_level = metadata.get('access_level', '') if isinstance(metadata, dict) else ''
        if meta_level in ('public', 'internal', 'executive', 'confidential'):
            return meta_level
        
        # Heuristic fallback — log so we can track legacy data migration
        logger.debug(f"access_level not set for {result.get('source_id')}, using source_type heuristic")

        # Executive profiles are executive-scope
        if source_type == 'executive_profile':
            return 'executive'
        
        # Decision cases
        if source_type == 'decision_case':
            # Check for explicit scope in metadata
            if 'scope' in metadata:
                return metadata['scope'].lower()
            
            # Infer from confidence level or category
            confidence = metadata.get('confidence', 0)
            category = metadata.get('category', '').lower()
            
            # High-confidence strategic decisions are executive-scope
            if confidence and float(confidence) > 0.8 or 'strategic' in category:
                return 'executive'
            
            # Default to internal for decisions
            return 'internal'
        
        # Policy documents
        if source_type == 'policy':
            # Check explicit confidentiality field
            if 'confidentiality' in metadata and metadata['confidentiality']:
                confidentiality = metadata['confidentiality'].lower()
                # Map confidentiality levels to scopes
                if confidentiality in ['public', 'internal', 'executive', 'confidential']:
                    return confidentiality
                elif confidentiality == 'company-wide':
                    return 'public'
                elif confidentiality in ['leadership', 'exec']:
                    return 'executive'
            
            # Default to internal for policies
            return 'internal'
        
        # Default: internal scope
        return 'internal'
    
    def get_role_info(self, role: str) -> Dict[str, Any]:
        """
        Get information about a role.
        
        Args:
            role: Role name
        
        Returns:
            Role information dictionary
        """
        if role not in self.roles:
            return {
                'valid': False,
                'error': f"Unknown role: {role}",
                'available_roles': list(self.roles.keys()),
            }
        
        role_data = self.roles[role]
        return {
            'valid': True,
            'role': role,
            'allowed_scopes': role_data['allowed_scopes'],
            'description': role_data['description'],
        }
    
    def can_access(self, role: str, scope: str) -> bool:
        """
        Check if a role can access a specific scope.
        
        Args:
            role: User role
            scope: Content scope
        
        Returns:
            True if role can access scope
        """
        if role not in self.roles:
            role = self.default_role
        
        allowed_scopes = self.roles[role]['allowed_scopes']
        return scope in allowed_scopes
    
    def get_allowed_scopes(self, role: str = None) -> List[str]:
        """
        Get list of allowed scopes for a role.

        Delegates to shared.rbac.get_allowed_scopes for consistency.

        Args:
            role: User role (defaults to default_role)

        Returns:
            List of allowed scope strings
        """
        role = role or self.default_role
        return _shared_get_allowed_scopes(role)
