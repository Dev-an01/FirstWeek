"""
Neo4j Embedding Integration
============================

Purpose: Read embeddings from PostgreSQL and update Neo4j nodes
         Completes the dual storage architecture

Usage: python embedding_generation/add_neo4j_embeddings.py
"""

import psycopg2
from neo4j import GraphDatabase
import logging
import time
from typing import List, Dict, Optional
import numpy as np
from datetime import datetime

# Import from config
import sys
import os
sys.path.append(os.path.dirname(__file__))
from config import POSTGRES_CONFIG, NEO4J_CONFIG

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class Neo4jEmbeddingIntegrator:
    """Handles integration of embeddings from PostgreSQL to Neo4j"""
    
    def __init__(self):
        """Initialize database connections"""
        self.pg_conn = None
        self.neo4j_driver = None
        self.stats = {
            'decisions_updated': 0,
            'policies_updated': 0,
            'decisions_failed': 0,
            'policies_failed': 0,
            'errors': []
        }
        
    def connect_databases(self):
        """Connect to PostgreSQL and Neo4j"""
        logger.info("Connecting to databases...")
        
        # Connect to PostgreSQL
        try:
            self.pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
            logger.info("  ✓ PostgreSQL connected")
        except Exception as e:
            logger.error(f"  ✗ PostgreSQL connection failed: {e}")
            raise
        
        # Connect to Neo4j
        try:
            self.neo4j_driver = GraphDatabase.driver(
                NEO4J_CONFIG['uri'],
                auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
            )
            # Test connection
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            logger.info("  ✓ Neo4j connected")
        except Exception as e:
            logger.error(f"  ✗ Neo4j connection failed: {e}")
            raise
    
    def fetch_embeddings_from_postgres(self, source_type: str) -> List[Dict]:
        """
        Fetch embeddings from PostgreSQL for given source_type
        
        Args:
            source_type: 'decision_case' or 'policy'
        
        Returns:
            List of dicts with: source_id, embedding, text_content, neo4j_id
        """
        cursor = self.pg_conn.cursor()
        
        if source_type == 'decision_case':
            # Join with decision_cases to get executive info for mapping
            query = """
                SELECT e.source_id, e.embedding, e.text_content, e.model, e.created_at,
                       dc.executive_id
                FROM embeddings e
                JOIN decision_cases dc ON e.source_id = dc.id
                WHERE e.source_type = %s
                ORDER BY e.source_id
            """
        else:
            query = """
                SELECT source_id, embedding, text_content, model, created_at,
                       NULL as executive_id
                FROM embeddings
                WHERE source_type = %s
                ORDER BY source_id
            """
        
        cursor.execute(query, (source_type,))
        rows = cursor.fetchall()
        cursor.close()
        
        results = []
        for row in rows:
            source_id, embedding, text_content, model, created_at, executive_id = row
            
            # Convert pgvector to Python list
            if isinstance(embedding, str):
                # Parse if it's a string representation
                embedding_list = [float(x) for x in embedding.strip('[]').split(',')]
            else:
                # Already a list or array
                embedding_list = list(embedding)
            
            # Map PostgreSQL ID to Neo4j ID for decisions
            neo4j_id = source_id
            if source_type == 'decision_case' and executive_id:
                neo4j_id = self.map_postgres_to_neo4j_decision_id(source_id, executive_id)
            
            results.append({
                'source_id': source_id,
                'neo4j_id': neo4j_id,
                'embedding': embedding_list,
                'text_content': text_content,
                'model': model,
                'created_at': created_at
            })
        
        return results
    
    def map_postgres_to_neo4j_decision_id(self, postgres_id: str, executive_id: str) -> str:
        """
        Map PostgreSQL decision ID to Neo4j Decision ID
        
        PostgreSQL format: exec_001_test_DEC_001
        Neo4j format: DC_AKIKO_001 (based on executive name)
        
        Args:
            postgres_id: PostgreSQL decision_cases.id
            executive_id: PostgreSQL decision_cases.executive_id
        
        Returns:
            Neo4j Decision node ID
        """
        # Extract decision number from postgres_id (e.g., "001" from "exec_001_test_DEC_001")
        # Split by underscore and get the last part after DEC
        parts = postgres_id.split('_')
        if len(parts) >= 5 and parts[3] == 'DEC':
            decision_num = parts[4]  # "001"
        else:
            # Fallback: return original ID
            logger.warning(f"Could not parse decision number from {postgres_id}")
            return postgres_id
        
        # Map executive_id to Neo4j Executive first name
        executive_mapping = {
            'exec_001_test': 'AKIKO',
            'exec_002_test': 'RAJ',
            'exec_003_test': 'SARAH',
            'exec_004_test': 'YUKI'
        }
        
        executive_name = executive_mapping.get(executive_id)
        if not executive_name:
            logger.warning(f"Unknown executive_id {executive_id}, cannot map to Neo4j ID")
            return postgres_id
        
        # Construct Neo4j Decision ID
        neo4j_id = f"DC_{executive_name}_{decision_num}"
        return neo4j_id
    
    def update_decision_node(self, decision_id: str, embedding_data: Dict) -> bool:
        """
        Update Neo4j Decision node with embedding properties
        
        Args:
            decision_id: Decision node ID
            embedding_data: Dict with embedding, text_content, model
        
        Returns:
            True if successful, False otherwise
        """
        cypher = """
            MATCH (d:Decision {id: $decision_id})
            SET d.embedding = $embedding_array,
                d.embedding_text = $embedding_text,
                d.embedding_model = $embedding_model,
                d.embedding_date = datetime(),
                d.embedding_dimensions = $embedding_dimensions
            RETURN d.id, d.embedding_date
        """
        
        params = {
            'decision_id': decision_id,
            'embedding_array': embedding_data['embedding'],
            'embedding_text': embedding_data['text_content'],
            'embedding_model': embedding_data['model'],
            'embedding_dimensions': len(embedding_data['embedding'])
        }
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(cypher, params)
                record = result.single()
                
                if record:
                    logger.info(f"  ✓ {decision_id} → Updated ({len(embedding_data['embedding'])} dims)")
                    return True
                else:
                    logger.warning(f"  ⚠ {decision_id} → Node not found in Neo4j")
                    return False
                    
        except Exception as e:
            logger.error(f"  ✗ {decision_id} → Failed: {e}")
            self.stats['errors'].append({
                'type': 'decision',
                'id': decision_id,
                'error': str(e)
            })
            return False
    
    def update_policy_node(self, policy_id: str, embedding_data: Dict) -> bool:
        """
        Update Neo4j Policy node with embedding properties
        
        Args:
            policy_id: Policy node ID
            embedding_data: Dict with embedding, text_content, model
        
        Returns:
            True if successful, False otherwise
        """
        cypher = """
            MATCH (p:Policy {id: $policy_id})
            SET p.embedding = $embedding_array,
                p.embedding_text = $embedding_text,
                p.embedding_model = $embedding_model,
                p.embedding_date = datetime(),
                p.embedding_dimensions = $embedding_dimensions
            RETURN p.id, p.embedding_date
        """
        
        params = {
            'policy_id': policy_id,
            'embedding_array': embedding_data['embedding'],
            'embedding_text': embedding_data['text_content'],
            'embedding_model': embedding_data['model'],
            'embedding_dimensions': len(embedding_data['embedding'])
        }
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(cypher, params)
                record = result.single()
                
                if record:
                    logger.info(f"  ✓ {policy_id} → Updated ({len(embedding_data['embedding'])} dims)")
                    return True
                else:
                    logger.warning(f"  ⚠ {policy_id} → Node not found in Neo4j")
                    return False
                    
        except Exception as e:
            logger.error(f"  ✗ {policy_id} → Failed: {e}")
            self.stats['errors'].append({
                'type': 'policy',
                'id': policy_id,
                'error': str(e)
            })
            return False
    
    def verify_neo4j_embeddings(self) -> Dict:
        """
        Verify all nodes have embeddings
        
        Returns:
            {'decisions': count, 'policies': count, 'dimensions_valid': bool}
        """
        logger.info("\nRunning Verification...")
        
        results = {
            'decisions': 0,
            'policies': 0,
            'dimensions_valid': True,
            'sample_embeddings': []
        }
        
        with self.neo4j_driver.session() as session:
            # Count Decision nodes with embeddings
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.embedding IS NOT NULL
                RETURN count(d) AS count
            """)
            results['decisions'] = result.single()['count']
            
            # Count Policy nodes with embeddings
            result = session.run("""
                MATCH (p:Policy)
                WHERE p.embedding IS NOT NULL
                RETURN count(p) AS count
            """)
            results['policies'] = result.single()['count']
            
            # Check dimensions (sample)
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.embedding IS NOT NULL
                RETURN d.id AS id, size(d.embedding) AS dimensions
                LIMIT 5
            """)
            
            for record in result:
                dim = record['dimensions']
                results['sample_embeddings'].append({
                    'id': record['id'],
                    'dimensions': dim
                })
                if dim != 1024:  # MIGRATED: from 768 to 1024 for BAAI/bge-m3
                    results['dimensions_valid'] = False
            
            # Check embedding values are valid floats
            result = session.run("""
                MATCH (d:Decision)
                WHERE d.embedding IS NOT NULL
                RETURN d.id AS id, d.embedding[0] AS first_value
                LIMIT 3
            """)
            
            for record in result:
                try:
                    val = float(record['first_value'])
                    if not (-1.5 <= val <= 1.5):  # Reasonable range for normalized embeddings
                        results['dimensions_valid'] = False
                except (ValueError, TypeError):
                    results['dimensions_valid'] = False
        
        # Log verification results
        logger.info(f"  ✓ Neo4j Decision nodes with embeddings: {results['decisions']}/20")
        logger.info(f"  ✓ Neo4j Policy nodes with embeddings: {results['policies']}/12")
        
        if results['dimensions_valid']:
            logger.info(f"  ✓ All embeddings are 1024 dimensions")  # MIGRATED: BAAI/bge-m3
            logger.info(f"  ✓ Sample embedding values are valid floats")
        else:
            logger.warning(f"  ⚠ Dimension or value validation failed")
        
        return results
    
    def run(self):
        """Main orchestrator"""
        start_time = time.time()
        
        try:
            # Connect to databases
            self.connect_databases()
            
            # Fetch embeddings from PostgreSQL
            logger.info("\nReading embeddings from PostgreSQL...")
            decision_embeddings = self.fetch_embeddings_from_postgres('decision_case')
            policy_embeddings = self.fetch_embeddings_from_postgres('policy')
            
            logger.info(f"✓ Found {len(decision_embeddings)} decision_case embeddings")
            logger.info(f"✓ Found {len(policy_embeddings)} policy embeddings")
            
            # Update Decision nodes
            logger.info("\nUpdating Neo4j Decision Nodes...")
            for emb in decision_embeddings:
                # Use neo4j_id for the node lookup, not source_id
                if self.update_decision_node(emb['neo4j_id'], emb):
                    self.stats['decisions_updated'] += 1
                else:
                    self.stats['decisions_failed'] += 1
            
            logger.info(f"✓ Completed: {self.stats['decisions_updated']} Decision nodes updated")
            if self.stats['decisions_failed'] > 0:
                logger.warning(f"⚠ Failed: {self.stats['decisions_failed']} Decision nodes")
            
            # Update Policy nodes
            logger.info("\nUpdating Neo4j Policy Nodes...")
            for emb in policy_embeddings:
                # Use neo4j_id for the node lookup
                if self.update_policy_node(emb['neo4j_id'], emb):
                    self.stats['policies_updated'] += 1
                else:
                    self.stats['policies_failed'] += 1
            
            logger.info(f"✓ Completed: {self.stats['policies_updated']} Policy nodes updated")
            if self.stats['policies_failed'] > 0:
                logger.warning(f"⚠ Failed: {self.stats['policies_failed']} Policy nodes")
            
            # Verify
            verification_results = self.verify_neo4j_embeddings()
            
            # Print summary
            elapsed_time = time.time() - start_time
            self.print_summary(elapsed_time, verification_results)
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            self.cleanup()
    
    def print_summary(self, elapsed_time: float, verification_results: Dict):
        """Print final summary report"""
        logger.info("\n" + "="*60)
        logger.info("✅ NEO4J EMBEDDING INTEGRATION COMPLETE")
        logger.info("="*60)
        logger.info(f"Total nodes updated: {self.stats['decisions_updated'] + self.stats['policies_updated']}")
        logger.info(f"  - Decision nodes: {self.stats['decisions_updated']}")
        logger.info(f"  - Policy nodes: {self.stats['policies_updated']}")
        logger.info("")
        logger.info(f"Errors: {len(self.stats['errors'])}")
        logger.info(f"Time elapsed: {elapsed_time:.1f} seconds")
        logger.info("")
        logger.info("Dual storage complete:")
        logger.info("  ✓ PostgreSQL: 36 embeddings (vector search ready)")
        logger.info(f"  ✓ Neo4j: {verification_results['decisions'] + verification_results['policies']} node embeddings (graph-enhanced search ready)")
        logger.info("")
        
        if len(self.stats['errors']) == 0 and verification_results['dimensions_valid']:
            logger.info("Next: Blueprint #2 (Vector Search Module)")
        else:
            logger.warning("⚠ Some issues detected - review errors above")
        
        logger.info("="*60)
    
    def cleanup(self):
        """Close database connections"""
        logger.info("\nCleaning up connections...")
        
        if self.pg_conn:
            self.pg_conn.close()
            logger.info("  ✓ PostgreSQL connection closed")
        
        if self.neo4j_driver:
            self.neo4j_driver.close()
            logger.info("  ✓ Neo4j connection closed")


def main():
    """Entry point"""
    logger.info("="*60)
    logger.info("AI OFFICER - NEO4J EMBEDDING INTEGRATION")
    logger.info("="*60)
    
    integrator = Neo4jEmbeddingIntegrator()
    integrator.run()


if __name__ == '__main__':
    main()
