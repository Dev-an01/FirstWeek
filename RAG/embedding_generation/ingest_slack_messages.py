"""
Slack Messages Ingestion Script.
Parses Slack messages from markdown file and stores embeddings in PostgreSQL.
"""

import logging
import re
import sys
from datetime import datetime
from typing import List, Dict, Any

import psycopg2
import numpy as np

from . import config
from .model_manager import EmbeddingModel
from .storage_writer import StorageWriter, connect_postgres, connect_neo4j

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


def parse_slack_messages(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse Slack messages from markdown file.
    Groups messages by topic/thread for better context.

    Args:
        file_path: Path to the slack messages markdown file

    Returns:
        List of message chunks with metadata
    """
    logger.info(f"Parsing Slack messages from: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by author headers (Sample Executive or other authors)
    # Pattern: "Sample Executive\n  [date]"
    message_pattern = r'(Sample Executive|Kiara|Masaru example|Zaid Alam)\n\s+(?:APP\s+)?(\d+\s+\w+(?:\s+at\s+[\d:]+\s+[AP]M)?|\w+\s+at\s+[\d:]+\s+[AP]M)'

    # Find all message boundaries
    messages = []
    current_pos = 0

    for match in re.finditer(message_pattern, content):
        if current_pos > 0:
            # Get the message content between previous match end and this match start
            msg_content = content[current_pos:match.start()].strip()
            if msg_content and len(msg_content) > 10:
                messages.append({
                    'author': prev_author,
                    'date': prev_date,
                    'content': msg_content
                })

        prev_author = match.group(1)
        prev_date = match.group(2)
        current_pos = match.end()

    # Don't forget the last message
    if current_pos > 0:
        msg_content = content[current_pos:].strip()
        if msg_content and len(msg_content) > 10:
            messages.append({
                'author': prev_author,
                'date': prev_date,
                'content': msg_content
            })

    # Filter to only sample's messages and group related messages
    sample_messages = [m for m in messages if m['author'] == 'Sample Executive']
    logger.info(f"  Found {len(sample_messages)} messages from sample")

    return sample_messages


def create_message_chunks(messages: List[Dict[str, Any]], max_chunk_size: int = 1500) -> List[Dict[str, Any]]:
    """
    Create meaningful chunks from messages.
    Groups related messages and handles long messages.

    Args:
        messages: List of parsed messages
        max_chunk_size: Maximum characters per chunk

    Returns:
        List of chunks ready for embedding
    """
    chunks = []
    current_chunk = []
    current_size = 0

    for msg in messages:
        msg_text = f"[{msg['date']}] {msg['content']}"
        msg_size = len(msg_text)

        # If single message is too long, split it
        if msg_size > max_chunk_size:
            # Save current chunk first
            if current_chunk:
                chunks.append({
                    'content': '\n\n'.join(current_chunk),
                    'message_count': len(current_chunk)
                })
                current_chunk = []
                current_size = 0

            # Split long message into paragraphs or sentences
            paragraphs = msg['content'].split('\n\n')
            for para in paragraphs:
                if len(para) > 50:  # Only include meaningful paragraphs
                    chunks.append({
                        'content': f"[{msg['date']}] {para}",
                        'message_count': 1
                    })
        else:
            # Add to current chunk if it fits
            if current_size + msg_size > max_chunk_size and current_chunk:
                chunks.append({
                    'content': '\n\n'.join(current_chunk),
                    'message_count': len(current_chunk)
                })
                current_chunk = []
                current_size = 0

            current_chunk.append(msg_text)
            current_size += msg_size

    # Don't forget the last chunk
    if current_chunk:
        chunks.append({
            'content': '\n\n'.join(current_chunk),
            'message_count': len(current_chunk)
        })

    logger.info(f"  Created {len(chunks)} chunks for embedding")
    return chunks


def prepare_slack_text(chunk: Dict[str, Any], executive_id: str = "sample_profile") -> str:
    """
    Prepare Slack message chunk for embedding.
    Adds context about the source and author.

    Args:
        chunk: Message chunk dict
        executive_id: ID of the executive

    Returns:
        Formatted text for embedding
    """
    text = f"""Slack Messages from sample_profile (CEO, Example Company)
Source: Internal Slack Communications
Executive: {executive_id}

{chunk['content']}"""

    return text


def ingest_slack_messages(
    file_path: str,
    executive_id: str = "sample_profile"
) -> Dict[str, Any]:
    """
    Main function to ingest Slack messages.

    Args:
        file_path: Path to slack messages file
        executive_id: Executive ID for association

    Returns:
        Stats dict with results
    """
    stats = {
        'total_messages': 0,
        'chunks_created': 0,
        'embeddings_stored': 0,
        'errors': 0
    }

    try:
        # Step 1: Parse messages
        logger.info("\n" + "="*60)
        logger.info("SLACK MESSAGES INGESTION")
        logger.info("="*60)

        messages = parse_slack_messages(file_path)
        stats['total_messages'] = len(messages)

        if not messages:
            logger.warning("No messages found to ingest")
            return stats

        # Step 2: Create chunks
        logger.info("\nCreating message chunks...")
        chunks = create_message_chunks(messages)
        stats['chunks_created'] = len(chunks)

        # Step 3: Initialize embedding model
        logger.info("\nLoading embedding model...")
        model = EmbeddingModel(device=config.DEVICE)

        # Step 4: Connect to database
        logger.info("\nConnecting to databases...")
        pg_conn = connect_postgres()
        neo4j_driver = connect_neo4j()
        writer = StorageWriter(pg_conn, neo4j_driver)

        # Step 5: Process each chunk
        logger.info("\nProcessing chunks...")
        for i, chunk in enumerate(chunks):
            try:
                # Prepare text
                text = prepare_slack_text(chunk, executive_id)

                # Generate embedding
                embedding = model.generate_embedding(text)

                # Create unique ID for this chunk
                source_id = f"slack_{executive_id}_{i:03d}"

                # Store in PostgreSQL
                success = writer.store_embedding_postgres(
                    source_type='slack_message',
                    source_id=source_id,
                    text_content=text,
                    embedding=embedding,
                    chunk_index=i
                )

                if success:
                    stats['embeddings_stored'] += 1
                    logger.info(f"  [{i+1}/{len(chunks)}] Stored chunk: {source_id}")
                else:
                    stats['errors'] += 1
                    logger.error(f"  [{i+1}/{len(chunks)}] Failed to store: {source_id}")

            except Exception as e:
                stats['errors'] += 1
                logger.error(f"  Error processing chunk {i}: {e}")

        # Cleanup
        pg_conn.close()
        if neo4j_driver:
            neo4j_driver.close()

        # Summary
        logger.info("\n" + "="*60)
        logger.info("INGESTION COMPLETE")
        logger.info("="*60)
        logger.info(f"Total messages parsed: {stats['total_messages']}")
        logger.info(f"Chunks created: {stats['chunks_created']}")
        logger.info(f"Embeddings stored: {stats['embeddings_stored']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("="*60)

        return stats

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        stats['errors'] += 1
        return stats


if __name__ == "__main__":
    import os

    # Default path to slack messages file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(
        script_dir,
        "..",
        "docs",
        "sample_data",
        "slack messages.md"
    )

    # Allow override via command line
    file_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    # Run ingestion
    stats = ingest_slack_messages(file_path)

    # Exit with error code if there were errors
    sys.exit(1 if stats['errors'] > 0 else 0)
