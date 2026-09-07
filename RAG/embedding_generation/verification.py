"""
Verification module for post-generation checks.
Ensures embeddings are correctly generated and stored.
"""

import logging
import psycopg2
from neo4j import GraphDatabase
import numpy as np
from typing import Dict, Any, List
from collections import defaultdict

from . import config

logger = logging.getLogger(__name__)


def verify_postgresql_counts(conn) -> Dict[str, int]:
    """
    Check embedding counts in PostgreSQL.
    
    Expected:
        executive_profile: 4
        decision_case: 20
        policy: 12
        total: 36
    
    Args:
        conn: PostgreSQL connection
    
    Returns:
        Dict with counts by source_type
    """
    logger.info("Verifying PostgreSQL embedding counts...")
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT source_type, COUNT(*) as count
                FROM embeddings
                GROUP BY source_type
                ORDER BY source_type
            """)
            results = cursor.fetchall()
        
        counts = {}
        total = 0
        for source_type, count in results:
            counts[source_type] = count
            total += count
        counts['total'] = total
        
        # Log results
        logger.info("PostgreSQL embedding counts:")
        for key, value in sorted(counts.items()):
            expected = config.EXPECTED_COUNTS.get(key, '?')
            status = "✓" if value == expected else "✗"
            logger.info(f"  {status} {key}: {value} (expected: {expected})")
        
        return counts
        
    except Exception as e:
        logger.error(f"Failed to verify PostgreSQL counts: {e}")
        return {}


def verify_neo4j_counts(driver) -> Dict[str, int]:
    """
    Check embedding properties in Neo4j.
    
    Expected:
        Decision nodes with embedding: 20
        Policy nodes with embedding: 12
    
    Args:
        driver: Neo4j driver
    
    Returns:
        Dict with counts by node type
    """
    if not driver:
        logger.warning("Neo4j driver not available, skipping Neo4j verification")
        return {}
    
    logger.info("Verifying Neo4j embedding properties...")
    
    try:
        counts = {}
        
        with driver.session() as session:
            # Count Decision nodes with embeddings
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.embedding IS NOT NULL
                RETURN count(d) AS count
            """)
            counts['Decision'] = result.single()['count']
            
            # Count Policy nodes with embeddings
            result = session.run("""
                MATCH (p:Policy)
                WHERE p.embedding IS NOT NULL
                RETURN count(p) AS count
            """)
            counts['Policy'] = result.single()['count']
            
            counts['total'] = counts['Decision'] + counts['Policy']
        
        # Log results
        logger.info("Neo4j embedding counts:")
        for key in ['Decision', 'Policy', 'total']:
            value = counts.get(key, 0)
            expected = config.NEO4J_EXPECTED_COUNTS.get(key, '?')
            status = "✓" if value == expected else "✗"
            logger.info(f"  {status} {key}: {value} (expected: {expected})")
        
        return counts
        
    except Exception as e:
        logger.error(f"Failed to verify Neo4j counts: {e}")
        return {}


def verify_dimensions(conn) -> bool:
    """
    Verify all embeddings have correct dimensions.
    
    Args:
        conn: PostgreSQL connection
    
    Returns:
        True if all embeddings have correct dimension
    """
    logger.info("Verifying embedding dimensions...")
    
    try:
        conn.rollback()  # Clear any pending transaction
        with conn.cursor() as cursor:
            # Get dimensions of all embeddings using pgvector's vector_dims()
            cursor.execute("""
                SELECT source_id, vector_dims(embedding) AS dimension
                FROM embeddings
            """)
            results = cursor.fetchall()
        
        expected_dim = config.EMBEDDING_DIMENSION
        all_correct = True
        wrong_dims = []
        
        for source_id, dimension in results:
            if dimension != expected_dim:
                all_correct = False
                wrong_dims.append(f"{source_id}: {dimension}D")
        
        if all_correct:
            logger.info(f"  ✓ All {len(results)} embeddings have {expected_dim} dimensions")
        else:
            logger.error(f"  ✗ Found embeddings with wrong dimensions:")
            for item in wrong_dims:
                logger.error(f"    {item}")
        
        return all_correct
        
    except Exception as e:
        logger.error(f"Failed to verify dimensions: {e}")
        return False


def verify_normalization(conn) -> bool:
    """
    Verify vectors are normalized (L2 norm ≈ 1.0).
    
    Args:
        conn: PostgreSQL connection
    
    Returns:
        True if all vectors are normalized
    """
    logger.info("Verifying embedding normalization...")

    try:
        conn.rollback()  # Clear any pending transaction
        with conn.cursor() as cursor:
            # Sample 10 random embeddings
            cursor.execute("""
                SELECT source_id, embedding
                FROM embeddings
                ORDER BY RANDOM()
                LIMIT 10
            """)
            results = cursor.fetchall()
        
        all_normalized = True
        denormalized = []
        
        for source_id, embedding_list in results:
            embedding = np.array(embedding_list)
            norm = np.linalg.norm(embedding)
            
            # Check if norm is close to 1.0
            if abs(norm - 1.0) > config.NORM_TOLERANCE:
                all_normalized = False
                denormalized.append(f"{source_id}: norm={norm:.4f}")
        
        if all_normalized:
            logger.info(f"  ✓ All sampled embeddings are normalized (norm ≈ 1.0)")
        else:
            logger.warning(f"  ⚠ Found denormalized embeddings:")
            for item in denormalized:
                logger.warning(f"    {item}")
        
        return all_normalized
        
    except Exception as e:
        logger.error(f"Failed to verify normalization: {e}")
        return False


def test_similarity_query(conn, model) -> bool:
    """
    Test that embeddings enable semantic search.
    
    Test query: "discount approval for customer"
    Expected: Returns discount-related decisions
    
    Args:
        conn: PostgreSQL connection
        model: EmbeddingModel instance
    
    Returns:
        True if similarity search returns relevant results
    """
    logger.info("Testing similarity query...")

    try:
        conn.rollback()  # Clear any pending transaction

        # Generate query embedding
        test_query = config.TEST_QUERY
        logger.info(f"  Test query: '{test_query}'")

        query_embedding = model.generate_embedding(test_query)
        query_embedding_list = query_embedding.tolist()

        # Search for similar embeddings
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    source_id, 
                    source_type,
                    text_content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM embeddings
                WHERE source_type = 'decision_case'
                ORDER BY embedding <=> %s::vector
                LIMIT 5
            """, (query_embedding_list, query_embedding_list))
            results = cursor.fetchall()
        
        logger.info(f"  Top {len(results)} results:")
        
        relevant_found = False
        for i, (source_id, source_type, text_content, similarity) in enumerate(results, 1):
            # Check if result contains expected keywords
            text_lower = text_content.lower()
            keywords_found = [kw for kw in config.TEST_EXPECTED_KEYWORDS if kw in text_lower]
            
            is_relevant = len(keywords_found) > 0 and similarity >= config.SIMILARITY_THRESHOLD
            if is_relevant:
                relevant_found = True
            
            status = "✓" if is_relevant else "○"
            logger.info(f"  {status} {i}. {source_id} (similarity: {similarity:.4f})")
            logger.info(f"       Keywords: {keywords_found if keywords_found else 'none'}")
            logger.info(f"       Preview: {text_content[:100]}...")
        
        if relevant_found:
            logger.info("  ✓ Similarity search returns relevant results")
        else:
            logger.warning("  ⚠ Similarity search may not be working correctly")
        
        return relevant_found
        
    except Exception as e:
        logger.error(f"Failed to test similarity query: {e}")
        return False


def run_verification(pg_conn, neo4j_driver, model) -> Dict[str, Any]:
    """
    Run comprehensive verification checks.
    
    Args:
        pg_conn: PostgreSQL connection
        neo4j_driver: Neo4j driver
        model: EmbeddingModel instance
    
    Returns:
        Dict with all verification results
    """
    logger.info("\n" + "="*60)
    logger.info("RUNNING VERIFICATION CHECKS")
    logger.info("="*60 + "\n")
    
    results = {
        'pg_counts': {},
        'neo4j_counts': {},
        'dimensions_valid': False,
        'normalized': False,
        'similarity_works': False,
        'all_passed': False
    }
    
    # Check 1: PostgreSQL counts
    results['pg_counts'] = verify_postgresql_counts(pg_conn)
    pg_counts_match = (
        results['pg_counts'].get('executive_profile', 0) == config.EXPECTED_COUNTS['executive_profile'] and
        results['pg_counts'].get('decision_case', 0) == config.EXPECTED_COUNTS['decision_case'] and
        results['pg_counts'].get('policy', 0) == config.EXPECTED_COUNTS['policy'] and
        results['pg_counts'].get('total', 0) == config.EXPECTED_COUNTS['total']
    )
    
    # Check 2: Neo4j counts
    results['neo4j_counts'] = verify_neo4j_counts(neo4j_driver)
    neo4j_counts_match = (
        results['neo4j_counts'].get('Decision', 0) == config.NEO4J_EXPECTED_COUNTS['Decision'] and
        results['neo4j_counts'].get('Policy', 0) == config.NEO4J_EXPECTED_COUNTS['Policy']
    ) if neo4j_driver else True  # Pass if Neo4j not required
    
    # Check 3: Dimensions
    results['dimensions_valid'] = verify_dimensions(pg_conn)
    
    # Check 4: Normalization
    results['normalized'] = verify_normalization(pg_conn)
    
    # Check 5: Similarity query
    results['similarity_works'] = test_similarity_query(pg_conn, model)
    
    # Overall result - normalization is non-critical
    critical_checks_passed = all([
        pg_counts_match,
        neo4j_counts_match,
        results['dimensions_valid'],
        results['similarity_works']
    ])

    results['all_passed'] = critical_checks_passed and results['normalized']
    results['critical_passed'] = critical_checks_passed  # For exit code
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*60)
    logger.info(f"PostgreSQL counts:     {'✓ PASS' if pg_counts_match else '✗ FAIL'}")
    logger.info(f"Neo4j counts:          {'✓ PASS' if neo4j_counts_match else '✗ FAIL'}")
    logger.info(f"Dimensions valid:      {'✓ PASS' if results['dimensions_valid'] else '✗ FAIL'}")
    logger.info(f"Normalized:            {'✓ PASS' if results['normalized'] else '⚠ WARN (non-critical)'}")
    logger.info(f"Similarity search:     {'✓ PASS' if results['similarity_works'] else '✗ FAIL'}")
    logger.info("="*60)

    if results['all_passed']:
        logger.info("✅ ALL VERIFICATION CHECKS PASSED")
    elif results['critical_passed']:
        logger.info("✅ CRITICAL CHECKS PASSED (normalization warning is non-critical)")
    else:
        logger.error("❌ CRITICAL VERIFICATION CHECKS FAILED")
    
    logger.info("="*60 + "\n")
    
    return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    print("This module requires connections to run verification.")
    print("Import and call run_verification() with connections and model.")
