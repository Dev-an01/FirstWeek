"""
Main orchestrator for embedding generation system.
Coordinates the entire process from data loading to verification.
"""

import logging
import time
import sys
from datetime import datetime
from typing import Dict, Any

import psycopg2

from . import config
from .text_preparation import (
    prepare_executive_profile_text,
    prepare_decision_case_text,
    prepare_policy_text,
    prepare_document_section_text,
    validate_text
)
from .model_manager import EmbeddingModel
from .storage_writer import StorageWriter, connect_postgres, connect_neo4j
from .verification import run_verification

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE) if config.LOG_TO_FILE else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)


def fetch_executive_profiles(conn):
    """Fetch all executive profiles from PostgreSQL."""
    logger.info("Fetching executive profiles...")
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, title, department, profile_data
            FROM executive_profiles
            ORDER BY id
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        profiles = [dict(zip(columns, row)) for row in rows]
    logger.info(f"  Found {len(profiles)} executive profiles")
    return profiles


def fetch_decision_cases(conn):
    """Fetch all decision cases from PostgreSQL."""
    logger.info("Fetching decision cases...")
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, executive_id, title, category, date,
                   situation, decision_made, rationale, outcome,
                   lessons_learned, confidence, precedent
            FROM decision_cases
            ORDER BY executive_id, id
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        decisions = [dict(zip(columns, row)) for row in rows]
    logger.info(f"  Found {len(decisions)} decision cases")
    return decisions


def fetch_policies(conn):
    """Fetch all policy documents from PostgreSQL."""
    logger.info("Fetching policy documents...")
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, version, content_markdown
            FROM policy_documents
            ORDER BY id
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        policies = [dict(zip(columns, row)) for row in rows]
    logger.info(f"  Found {len(policies)} policy documents")
    return policies


def process_executive_profiles(profiles, model, writer, stats):
    """
    Process and embed all executive profiles.
    
    Args:
        profiles: List of profile dicts
        model: EmbeddingModel instance
        writer: StorageWriter instance
        stats: Stats dict to update
    """
    logger.info("\n" + "="*60)
    logger.info("PROCESSING EXECUTIVE PROFILES")
    logger.info("="*60)
    
    for i, profile in enumerate(profiles, 1):
        try:
            profile_id = profile['id']
            profile_name = profile.get('name', 'Unknown')
            
            logger.info(f"\n[{i}/{len(profiles)}] Processing: {profile_name} ({profile_id})")
            
            # Prepare text
            embedding_text = prepare_executive_profile_text(profile)
            
            # Validate
            if not validate_text(embedding_text):
                logger.error(f"  ✗ Invalid text for {profile_id}, skipping")
                stats['errors'] += 1
                continue
            
            # Generate embedding
            embedding = model.generate_embedding(embedding_text)
            logger.info(f"  ✓ Generated {len(embedding)}-dim embedding")
            
            # Store in PostgreSQL only (profiles don't go to Neo4j)
            success = writer.store_embedding_postgres(
                source_type='executive_profile',
                source_id=profile_id,
                text_content=embedding_text,
                embedding=embedding
            )
            
            if success:
                logger.info(f"  ✓ Stored in PostgreSQL")
                stats['executives'] += 1
                stats['total'] += 1
            else:
                logger.error(f"  ✗ Storage failed")
                stats['errors'] += 1
                
        except Exception as e:
            logger.error(f"  ✗ Error processing {profile.get('id', 'unknown')}: {e}")
            stats['errors'] += 1
    
    logger.info(f"\n✓ Completed: {stats['executives']} executive profiles")


def process_decision_cases(decisions, model, writer, stats):
    """
    Process and embed all decision cases.
    
    Args:
        decisions: List of decision dicts
        model: EmbeddingModel instance
        writer: StorageWriter instance
        stats: Stats dict to update
    """
    logger.info("\n" + "="*60)
    logger.info("PROCESSING DECISION CASES")
    logger.info("="*60)
    
    for i, decision in enumerate(decisions, 1):
        try:
            decision_id = decision['id']
            decision_title = decision.get('title', 'Untitled')
            
            logger.info(f"\n[{i}/{len(decisions)}] Processing: {decision_title}")
            logger.info(f"  ID: {decision_id}")
            
            # Prepare text
            embedding_text = prepare_decision_case_text(decision)
            
            # Validate
            if not validate_text(embedding_text):
                logger.error(f"  ✗ Invalid text for {decision_id}, skipping")
                stats['errors'] += 1
                continue
            
            # Generate embedding
            embedding = model.generate_embedding(embedding_text)
            logger.info(f"  ✓ Generated {len(embedding)}-dim embedding")
            
            # Store in PostgreSQL
            pg_success = writer.store_embedding_postgres(
                source_type='decision_case',
                source_id=decision_id,
                text_content=embedding_text,
                embedding=embedding
            )
            
            if pg_success:
                logger.info(f"  ✓ Stored in PostgreSQL")
            else:
                logger.error(f"  ✗ PostgreSQL storage failed")
                stats['errors'] += 1
                continue
            
            # Store in Neo4j
            neo4j_success = writer.store_embedding_neo4j_decision(
                decision_id=decision_id,
                embedding=embedding,
                embedding_text=embedding_text
            )
            
            if neo4j_success:
                logger.info(f"  ✓ Updated Neo4j Decision node")
            else:
                logger.warning(f"  ⚠ Neo4j update failed (non-critical)")
            
            stats['decisions'] += 1
            stats['total'] += 1
                
        except Exception as e:
            logger.error(f"  ✗ Error processing {decision.get('id', 'unknown')}: {e}")
            stats['errors'] += 1
    
    logger.info(f"\n✓ Completed: {stats['decisions']} decision cases")


def process_policies(policies, model, writer, stats):
    """
    Process and embed all policy documents.
    
    Args:
        policies: List of policy dicts
        model: EmbeddingModel instance
        writer: StorageWriter instance
        stats: Stats dict to update
    """
    logger.info("\n" + "="*60)
    logger.info("PROCESSING POLICY DOCUMENTS")
    logger.info("="*60)
    
    for i, policy in enumerate(policies, 1):
        try:
            policy_id = policy['id']
            policy_name = policy.get('name', 'Untitled Policy')
            
            logger.info(f"\n[{i}/{len(policies)}] Processing: {policy_name}")
            logger.info(f"  ID: {policy_id}")
            
            # Prepare text
            embedding_text = prepare_policy_text(policy, max_length=config.MAX_TEXT_LENGTH)
            
            # Validate
            if not validate_text(embedding_text):
                logger.error(f"  ✗ Invalid text for {policy_id}, skipping")
                stats['errors'] += 1
                continue
            
            # Generate embedding
            embedding = model.generate_embedding(embedding_text)
            logger.info(f"  ✓ Generated {len(embedding)}-dim embedding")
            
            # Store in PostgreSQL
            pg_success = writer.store_embedding_postgres(
                source_type='policy',
                source_id=policy_id,
                text_content=embedding_text,
                embedding=embedding
            )
            
            if pg_success:
                logger.info(f"  ✓ Stored in PostgreSQL")
            else:
                logger.error(f"  ✗ PostgreSQL storage failed")
                stats['errors'] += 1
                continue
            
            # Store in Neo4j
            neo4j_success = writer.store_embedding_neo4j_policy(
                policy_id=policy_id,
                embedding=embedding,
                embedding_text=embedding_text
            )
            
            if neo4j_success:
                logger.info(f"  ✓ Updated Neo4j Policy node")
            else:
                logger.warning(f"  ⚠ Neo4j update failed (non-critical)")
            
            stats['policies'] += 1
            stats['total'] += 1
                
        except Exception as e:
            logger.error(f"  ✗ Error processing {policy.get('id', 'unknown')}: {e}")
            stats['errors'] += 1
    
    logger.info(f"\n✓ Completed: {stats['policies']} policy documents")


def fetch_document_sections(conn):
    """Fetch all document sections from PostgreSQL."""
    logger.info("Fetching document sections...")
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, parent_document_id, parent_document_type,
                   section_number, section_title, content, word_count,
                   section_type
            FROM document_sections
            ORDER BY parent_document_id, section_number
        """)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        sections = [dict(zip(columns, row)) for row in rows]
    logger.info(f"  Found {len(sections)} document sections")
    return sections


def process_document_sections(sections, model, writer, stats):
    """
    Process and embed all document sections.

    Args:
        sections: List of section dicts from document_sections table
        model: EmbeddingModel instance
        writer: StorageWriter instance
        stats: Stats dict to update
    """
    logger.info("\n" + "="*60)
    logger.info("PROCESSING DOCUMENT SECTIONS")
    logger.info("="*60)

    for i, section in enumerate(sections, 1):
        try:
            section_id = section['id']
            section_title = section.get('section_title', 'Untitled')

            logger.info(f"\n[{i}/{len(sections)}] Processing: {section_title}")
            logger.info(f"  ID: {section_id}")

            # Prepare text
            embedding_text = prepare_document_section_text(section)

            # Validate
            if not validate_text(embedding_text):
                logger.error(f"  ✗ Invalid text for {section_id}, skipping")
                stats['errors'] += 1
                continue

            # Generate embedding
            embedding = model.generate_embedding(embedding_text)
            logger.info(f"  ✓ Generated {len(embedding)}-dim embedding")

            # Store in section_embeddings table
            success = _store_section_embedding(
                writer.pg_conn, section_id, embedding_text, embedding
            )

            if success:
                logger.info(f"  ✓ Stored in section_embeddings")
                stats['sections'] += 1
                stats['total'] += 1
            else:
                logger.error(f"  ✗ Storage failed")
                stats['errors'] += 1

        except Exception as e:
            logger.error(f"  ✗ Error processing {section.get('id', 'unknown')}: {e}")
            stats['errors'] += 1

    logger.info(f"\n✓ Completed: {stats['sections']} document sections")


def _store_section_embedding(conn, section_id, text_content, embedding):
    """Store embedding in section_embeddings table."""
    try:
        import numpy as np
        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)

        sql = """
            INSERT INTO section_embeddings (section_id, text_content, embedding, model, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (section_id)
            DO UPDATE SET
                text_content = EXCLUDED.text_content,
                embedding = EXCLUDED.embedding,
                model = EXCLUDED.model,
                created_at = CURRENT_TIMESTAMP
            RETURNING id;
        """

        with conn.cursor() as cursor:
            cursor.execute(sql, (
                section_id,
                text_content,
                embedding_list,
                config.MODEL_NAME,
            ))
            conn.commit()

        return True

    except Exception as e:
        logger.error(f"Failed to store section embedding: {e}")
        conn.rollback()
        return False


def generate_missing_section_embeddings():
    """Generate embeddings for document_sections that don't have entries in section_embeddings."""
    pg_conn = connect_postgres()
    try:
        with pg_conn.cursor() as cur:
            cur.execute("""
                SELECT ds.id, ds.parent_document_id, ds.parent_document_type,
                       ds.section_number, ds.section_title, ds.content,
                       ds.word_count, ds.section_type
                FROM document_sections ds
                LEFT JOIN section_embeddings se ON ds.id = se.section_id
                WHERE se.id IS NULL
                ORDER BY ds.parent_document_id, ds.section_number
            """)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            sections = [dict(zip(columns, row)) for row in rows]

        if not sections:
            logger.info("No orphaned document sections found — all sections have embeddings.")
            return 0

        logger.info(f"Found {len(sections)} document sections without embeddings. Generating...")
        model = EmbeddingModel(device=config.DEVICE)
        count = 0
        for i, section in enumerate(sections, 1):
            try:
                text = prepare_document_section_text(section)
                if not validate_text(text):
                    continue
                embedding = model.generate_embedding(text)
                if _store_section_embedding(pg_conn, section['id'], text, embedding):
                    count += 1
                    logger.info(f"  [{i}/{len(sections)}] ✓ {section.get('section_title', section['id'])}")
            except Exception as e:
                logger.error(f"  [{i}/{len(sections)}] ✗ {section['id']}: {e}")

        logger.info(f"Generated {count} section embeddings.")
        return count
    finally:
        pg_conn.close()


def print_summary_report(stats, verification_results, elapsed_time):
    """Print final summary report."""
    logger.info("\n" + "="*60)
    logger.info("✅ EMBEDDING GENERATION COMPLETE")
    logger.info("="*60)
    logger.info(f"Total embedded:        {stats['total']}")
    logger.info(f"  - Executive profiles: {stats['executives']}")
    logger.info(f"  - Decision cases:     {stats['decisions']}")
    logger.info(f"  - Policy documents:   {stats['policies']}")
    logger.info(f"  - Document sections:  {stats['sections']}")
    logger.info(f"Errors:                {stats['errors']}")
    logger.info("")
    logger.info(f"Time elapsed:          {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    
    if stats['total'] > 0:
        logger.info(f"Average time per item: {elapsed_time/stats['total']:.2f} seconds")
    
    logger.info("")
    logger.info("Verification:")
    if verification_results.get('all_passed'):
        logger.info("  ✅ ALL CHECKS PASSED")
    elif verification_results.get('critical_passed'):
        logger.info("  ✅ CRITICAL CHECKS PASSED (normalization warning is non-critical)")
    else:
        logger.info("  ❌ CRITICAL CHECKS FAILED (see verification details above)")
    
    logger.info("="*60 + "\n")


def main():
    """Main orchestrator for embedding generation."""
    print("\n" + "="*60)
    print("AI OFFICER - EMBEDDING GENERATION SYSTEM")
    print("="*60)
    print(f"Model: {config.MODEL_NAME}")
    print(f"Dimensions: {config.EMBEDDING_DIMENSION}")
    print(f"Device: {config.DEVICE}")
    print(f"Target: {config.EXPECTED_COUNTS['total']} embeddings")
    print("="*60 + "\n")
    
    # Initialize stats
    stats = {
        'total': 0,
        'executives': 0,
        'decisions': 0,
        'policies': 0,
        'sections': 0,
        'errors': 0
    }
    
    start_time = time.time()
    
    try:
        # Step 1: Initialize model
        logger.info("STEP 1: Loading embedding model...")
        model = EmbeddingModel(device=config.DEVICE)
        
        # Display GPU info
        gpu_info = model.get_gpu_info()
        if gpu_info.get('available'):
            logger.info(f"  GPU: {gpu_info.get('device_name', 'Unknown')}")
            logger.info(f"  VRAM: {gpu_info.get('memory_total_gb', 0):.2f} GB")
        else:
            logger.info("  Running on CPU")
        
        # Step 2: Connect to databases
        logger.info("\nSTEP 2: Connecting to databases...")
        pg_conn = connect_postgres()
        neo4j_driver = connect_neo4j()
        
        # Step 3: Initialize storage writer
        logger.info("\nSTEP 3: Initializing storage writer...")
        writer = StorageWriter(pg_conn, neo4j_driver)
        logger.info("  ✓ Storage writer ready")
        
        # Step 4: Fetch all data
        logger.info("\nSTEP 4: Fetching data from database...")
        profiles = fetch_executive_profiles(pg_conn)
        decisions = fetch_decision_cases(pg_conn)
        policies = fetch_policies(pg_conn)
        sections = fetch_document_sections(pg_conn)

        total_items = len(profiles) + len(decisions) + len(policies) + len(sections)
        logger.info(f"\n  Total items to process: {total_items}")
        
        # Step 5: Process executive profiles
        logger.info("\nSTEP 5: Processing executive profiles...")
        process_executive_profiles(profiles, model, writer, stats)
        
        # Step 6: Process decision cases
        logger.info("\nSTEP 6: Processing decision cases...")
        process_decision_cases(decisions, model, writer, stats)
        
        # Step 7: Process policies
        logger.info("\nSTEP 7: Processing policy documents...")
        process_policies(policies, model, writer, stats)

        # Step 8: Process document sections
        logger.info("\nSTEP 8: Processing document sections...")
        process_document_sections(sections, model, writer, stats)

        # Step 9: Verification
        logger.info("\nSTEP 9: Running verification checks...")
        verification_results = run_verification(pg_conn, neo4j_driver, model)
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        
        # Step 10: Print summary report
        print_summary_report(stats, verification_results, elapsed_time)
        
        # Cleanup
        logger.info("Cleaning up connections...")
        pg_conn.close()
        if neo4j_driver:
            neo4j_driver.close()
        logger.info("✓ Connections closed")
        
        # Return success/failure code (critical checks must pass, normalization is optional)
        return 0 if verification_results.get('critical_passed', verification_results.get('all_passed')) else 1
        
    except KeyboardInterrupt:
        logger.warning("\n\n⚠ Process interrupted by user")
        return 2
        
    except Exception as e:
        logger.error(f"\n\n✗ FATAL ERROR: {e}")
        logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
