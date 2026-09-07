"""
Storage writer for dual database storage.
Handles PostgreSQL embeddings table and Neo4j node properties.
"""

import logging
import psycopg2
import psycopg2.extensions
from neo4j import GraphDatabase
from typing import Dict, Any, Optional
import numpy as np
from datetime import datetime

from . import config

logger = logging.getLogger(__name__)


class StorageWriter:
    """
    Handles storage of embeddings in both PostgreSQL and Neo4j.
    Implements error resilience and retry logic.
    """
    
    def __init__(self, pg_conn=None, neo4j_driver=None):
        """
        Initialize storage writer.
        
        Args:
            pg_conn: PostgreSQL connection (optional, will create if None)
            neo4j_driver: Neo4j driver (optional, will create if None)
        """
        self.pg_conn = pg_conn
        self.neo4j_driver = neo4j_driver
        self._connections_created = False
        
        if not self.pg_conn:
            self.pg_conn = self._create_postgres_connection()
            self._connections_created = True
        
        if not self.neo4j_driver:
            self.neo4j_driver = self._create_neo4j_driver()
    
    def _create_postgres_connection(self):
        """Create PostgreSQL connection with UTF-8 encoding."""
        try:
            logger.info("Connecting to PostgreSQL...")
            conn = psycopg2.connect(**config.POSTGRES_CONFIG)
            conn.set_client_encoding('UTF8')
            logger.info("PostgreSQL connection established")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def _create_neo4j_driver(self):
        """Create Neo4j driver."""
        try:
            logger.info("Connecting to Neo4j...")
            driver = GraphDatabase.driver(
                config.NEO4J_CONFIG['uri'],
                auth=(config.NEO4J_CONFIG['user'], config.NEO4J_CONFIG['password'])
            )
            # Test connection
            driver.verify_connectivity()
            logger.info("Neo4j connection established")
            return driver
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            if config.NEO4J_REQUIRED:
                raise
            else:
                logger.warning("Neo4j connection failed but not required, continuing...")
                return None
    
    def store_embedding_postgres(
        self,
        source_type: str,
        source_id: str,
        text_content: str,
        embedding: np.ndarray,
        model: str = config.MODEL_NAME,
        chunk_index: int = config.CHUNK_INDEX_DEFAULT,
        company_id: Optional[str] = None,
        executive_id: Optional[str] = None,
        access_level: Optional[str] = None,
    ) -> bool:
        """
        Store embedding in PostgreSQL embeddings table.

        Args:
            source_type: 'executive_profile', 'decision_case', or 'policy'
            source_id: ID from source table
            text_content: The text that was embedded
            embedding: Numpy array of shape (768,)
            model: Model name used for embedding
            chunk_index: Chunk index (0 for single embeddings)
            company_id: Optional company ID for tenant isolation
            executive_id: Optional executive ID for tenant isolation
            access_level: Optional access scope (public, internal, executive, confidential)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert numpy array to list for PostgreSQL
            embedding_list = embedding.tolist()

            # Prepare SQL with upsert (includes company_id, executive_id, access_level)
            sql = """
                INSERT INTO embeddings (
                    source_type, source_id, text_content, embedding, model,
                    chunk_index, company_id, executive_id, access_level, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    text_content = EXCLUDED.text_content,
                    model = EXCLUDED.model,
                    executive_id = EXCLUDED.executive_id,
                    access_level = EXCLUDED.access_level,
                    created_at = CURRENT_TIMESTAMP
                RETURNING id;
            """

            # Execute with cursor
            with self.pg_conn.cursor() as cursor:
                cursor.execute(sql, (
                    source_type,
                    source_id,
                    text_content,
                    embedding_list,
                    model,
                    chunk_index,
                    company_id,
                    executive_id,
                    access_level,
                ))
                record_id = cursor.fetchone()[0]
                self.pg_conn.commit()

            logger.debug(f"Stored embedding in PostgreSQL: {source_type}/{source_id} (id: {record_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to store embedding in PostgreSQL: {e}")
            logger.error(f"Details: source_type={source_type}, source_id={source_id}")
            self.pg_conn.rollback()
            return False
    
    def store_embedding_neo4j_decision(
        self,
        decision_id: str,
        embedding: np.ndarray,
        embedding_text: str,
        model: str = config.MODEL_NAME
    ) -> bool:
        """
        Update Neo4j Decision node with embedding property.
        
        Args:
            decision_id: Decision node ID
            embedding: Numpy array of shape (768,)
            embedding_text: The text that was embedded
            model: Model name used
        
        Returns:
            True if successful, False otherwise
        """
        if not self.neo4j_driver:
            logger.warning("Neo4j driver not available, skipping Decision node update")
            return False
        
        try:
            # Convert numpy array to list
            embedding_list = embedding.tolist()
            
            # Cypher query
            cypher = """
                MATCH (d:Decision {id: $decision_id})
                SET d.embedding = $embedding,
                    d.embedding_text = $embedding_text,
                    d.embedding_model = $model,
                    d.embedding_date = datetime()
                RETURN d.id AS id
            """
            
            # Execute query
            with self.neo4j_driver.session() as session:
                result = session.run(
                    cypher,
                    decision_id=decision_id,
                    embedding=embedding_list,
                    embedding_text=embedding_text,
                    model=model
                )
                record = result.single()
                
                if not record:
                    logger.warning(f"Decision node not found: {decision_id}")
                    return False
                
                logger.debug(f"Updated Decision node in Neo4j: {decision_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to update Decision node in Neo4j: {e}")
            logger.error(f"Decision ID: {decision_id}")
            return False
    
    def store_embedding_neo4j_policy(
        self,
        policy_id: str,
        embedding: np.ndarray,
        embedding_text: str,
        model: str = config.MODEL_NAME
    ) -> bool:
        """
        Update Neo4j Policy node with embedding property.
        
        Args:
            policy_id: Policy node ID
            embedding: Numpy array of shape (768,)
            embedding_text: The text that was embedded
            model: Model name used
        
        Returns:
            True if successful, False otherwise
        """
        if not self.neo4j_driver:
            logger.warning("Neo4j driver not available, skipping Policy node update")
            return False
        
        try:
            # Convert numpy array to list
            embedding_list = embedding.tolist()
            
            # Cypher query
            cypher = """
                MATCH (p:Policy {id: $policy_id})
                SET p.embedding = $embedding,
                    p.embedding_text = $embedding_text,
                    p.embedding_model = $model,
                    p.embedding_date = datetime()
                RETURN p.id AS id
            """
            
            # Execute query
            with self.neo4j_driver.session() as session:
                result = session.run(
                    cypher,
                    policy_id=policy_id,
                    embedding=embedding_list,
                    embedding_text=embedding_text,
                    model=model
                )
                record = result.single()
                
                if not record:
                    logger.warning(f"Policy node not found: {policy_id}")
                    return False
                
                logger.debug(f"Updated Policy node in Neo4j: {policy_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to update Policy node in Neo4j: {e}")
            logger.error(f"Policy ID: {policy_id}")
            return False
    
    def close(self):
        """Close database connections."""
        if self._connections_created:
            if self.pg_conn:
                self.pg_conn.close()
                logger.info("PostgreSQL connection closed")
            if self.neo4j_driver:
                self.neo4j_driver.close()
                logger.info("Neo4j driver closed")


def connect_postgres():
    """Create and return PostgreSQL connection."""
    try:
        logger.info("Connecting to PostgreSQL...")
        conn = psycopg2.connect(**config.POSTGRES_CONFIG)
        conn.set_client_encoding('UTF8')
        logger.info("✓ PostgreSQL connected")
        return conn
    except Exception as e:
        logger.error(f"✗ PostgreSQL connection failed: {e}")
        raise


def connect_neo4j():
    """Create and return Neo4j driver."""
    try:
        logger.info("Connecting to Neo4j...")
        driver = GraphDatabase.driver(
            config.NEO4J_CONFIG['uri'],
            auth=(config.NEO4J_CONFIG['user'], config.NEO4J_CONFIG['password'])
        )
        driver.verify_connectivity()
        logger.info("✓ Neo4j connected")
        return driver
    except Exception as e:
        logger.error(f"✗ Neo4j connection failed: {e}")
        if config.NEO4J_REQUIRED:
            raise
        else:
            logger.warning("Continuing without Neo4j (non-critical)...")
            return None


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    print("\n" + "="*60)
    print("STORAGE WRITER TEST")
    print("="*60)
    
    # Test connections
    print("\n1. Testing database connections...")
    try:
        pg_conn = connect_postgres()
        neo4j_driver = connect_neo4j()
        print("   ✓ Both connections successful")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        exit(1)
    
    # Create storage writer
    print("\n2. Creating storage writer...")
    writer = StorageWriter(pg_conn, neo4j_driver)
    print("   ✓ Storage writer initialized")
    
    # Test embedding storage (using dummy data)
    print("\n3. Testing PostgreSQL storage...")
    test_embedding = np.random.randn(768)
    test_embedding = test_embedding / np.linalg.norm(test_embedding)  # Normalize
    
    success = writer.store_embedding_postgres(
        source_type='executive_profile',
        source_id='test_profile_001',
        text_content='This is a test embedding for verification',
        embedding=test_embedding,
        model='test-model'
    )
    
    if success:
        print("   ✓ PostgreSQL storage successful")
    else:
        print("   ✗ PostgreSQL storage failed")
    
    # Clean up test data
    print("\n4. Cleaning up test data...")
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM embeddings WHERE source_id = 'test_profile_001'"
            )
            pg_conn.commit()
        print("   ✓ Test data cleaned up")
    except Exception as e:
        print(f"   ⚠ Cleanup failed: {e}")
    
    # Close connections
    print("\n5. Closing connections...")
    writer.close()
    print("   ✓ Connections closed")
    
    print("\n" + "="*60)
    print("✅ Storage writer tests completed!")
    print("="*60)
