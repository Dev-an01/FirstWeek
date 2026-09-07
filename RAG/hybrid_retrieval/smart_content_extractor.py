"""
Smart Content Extractor with Section-Aware Selection and MMR
Combines best practices from ChatGPT, Gemini, and GLM recommendations.
"""

import re
import numpy as np
from typing import List, Dict, Tuple, Optional
from sentence_transformers import SentenceTransformer, util
import logging

logger = logging.getLogger(__name__)


class SmartContentExtractor:
    """
    Intelligent content extraction combining:
    - Section-aware regex detection (ChatGPT)
    - Semantic sentence ranking (Gemini)
    - MMR for diversity (ChatGPT)
    - Metric preservation (All 3 AIs)
    """

    def __init__(self, model_name: str = 'BAAI/bge-m3'):
        """
        Initialize the extractor.

        Args:
            model_name: Sentence transformer model (default: BAAI/bge-m3 multilingual)
        """
        # Reuse your existing embedding model (already on GPU)
        logger.info(f"Initializing SmartContentExtractor with model: {model_name}")
        self.sentence_model = SentenceTransformer(model_name)

        # Section detection patterns (ChatGPT recommendation + your domain)
        self.OUTCOME_HINTS = [
            r"\boutcome[s]?\b", r"\bresult[s]?\b", r"\bdecision[s]?\b",
            r"\baction[s]?\s*taken\b", r"\baction[s]?\b", r"\bremediation\b",
            r"\bresolution\b", r"\bmitigation\b", r"\bnext step[s]?\b",
            r"\bimpact\b", r"\bbudget\b", r"\bcompliance\b", r"\baudit[s]?\b",
            r"\bSLA\b", r"\bKPI[s]?\b", r"\bmeasures?\b",
            r"\bimplemented\b", r"\bachieved\b", r"\bcompleted\b",
            r"\bapproved\b", r"\binitiated\b", r"\bexecuted\b",
            # Japanese patterns for your executives
            r"\b実施\b", r"\b成果\b", r"\b結果\b", r"\b決定\b"
        ]

        # Metric patterns for protection (never compress these)
        self.METRIC_PATTERNS = [
            r'¥\d+[.,]?\d*[MBKmillion億万]*',  # Japanese yen with units
            r'\$\d+[.,]?\d*[MBKmillion]*',      # US dollars
            r'€\d+[.,]?\d*[MBKmillion]*',       # Euros
            r'\d+[.,]?\d*%',                     # Percentages
            r'\d{4}-\d{2}-\d{2}',               # Dates (YYYY-MM-DD)
            r'\d{1,2}/\d{1,2}/\d{4}',           # Dates (MM/DD/YYYY)
            r'SOC\s*\d+',                        # SOC compliance
            r'ISO\s*\d+',                        # ISO standards
            r'Type\s*[I]+',                      # Type I/II/III
            r'\d+[.,]?\d*\s*(million|billion|trillion|億|万)',  # Large numbers with units
        ]

        logger.info(f"✅ SmartContentExtractor initialized with {len(self.OUTCOME_HINTS)} outcome patterns")

    def find_outcome_spans(self, text: str, max_hits: int = 8) -> List[Tuple[int, int]]:
        """
        Find text spans around outcome/result/decision keywords.
        ChatGPT's section-aware approach with windowing.

        Args:
            text: Document text
            max_hits: Maximum number of spans to return

        Returns:
            List of (start, end) tuples for outcome-related spans
        """
        spans = []

        # Find all matches for outcome patterns
        for pattern in self.OUTCOME_HINTS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                # Expand window around match (±400 chars per ChatGPT recommendation)
                start = max(match.start() - 400, 0)
                end = min(match.end() + 1200, len(text))
                spans.append((start, end))

        if not spans:
            # Fallback: return beginning of document
            return [(0, min(2000, len(text)))]

        # Merge overlapping spans
        spans = sorted(spans)
        merged = []
        for start, end in spans:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)

        # Convert back to tuples and limit
        result = [tuple(span) for span in merged[:max_hits]]

        logger.debug(f"Found {len(result)} outcome spans in document of {len(text)} chars")
        return result

    def contains_metrics(self, text: str) -> bool:
        """
        Check if text contains important metrics.

        Args:
            text: Text to check

        Returns:
            True if text contains metrics
        """
        return any(re.search(pattern, text) for pattern in self.METRIC_PATTERNS)

    def mmr_selection(
        self,
        query_vec: np.ndarray,
        candidate_vecs: List[np.ndarray],
        lambda_mult: float = 0.7,
        k: int = 8
    ) -> List[int]:
        """
        Maximal Marginal Relevance for diversity.
        ChatGPT's MMR implementation.

        Args:
            query_vec: Query embedding
            candidate_vecs: List of candidate embeddings
            lambda_mult: Balance between relevance (λ) and diversity (1-λ)
            k: Number of items to select

        Returns:
            List of selected indices
        """
        selected = []
        candidates = list(range(len(candidate_vecs)))

        # Pre-compute similarity to query
        scores = [
            float(np.dot(query_vec, cv) / (np.linalg.norm(query_vec) * np.linalg.norm(cv) + 1e-8))
            for cv in candidate_vecs
        ]

        while candidates and len(selected) < k:
            mmr_scores = []
            for idx in candidates:
                # Relevance to query
                sim_to_query = scores[idx]

                # Redundancy with already selected
                if selected:
                    sim_to_selected = max(
                        float(np.dot(candidate_vecs[idx], candidate_vecs[s]) /
                             (np.linalg.norm(candidate_vecs[idx]) * np.linalg.norm(candidate_vecs[s]) + 1e-8))
                        for s in selected
                    )
                else:
                    sim_to_selected = 0.0

                # MMR score: λ * relevance - (1-λ) * redundancy
                mmr_score = lambda_mult * sim_to_query - (1 - lambda_mult) * sim_to_selected
                mmr_scores.append(mmr_score)

            # Select best MMR score
            best_idx = candidates[int(np.argmax(mmr_scores))]
            selected.append(best_idx)
            candidates.remove(best_idx)

        return selected

    def extract_relevant_content(
        self,
        query: str,
        documents: List[Dict],
        max_chars_per_doc: int = 1200,
        max_docs: int = 6
    ) -> List[Dict]:
        """
        Main extraction method combining all techniques.

        Args:
            query: User query
            documents: List of retrieved documents with 'content' field
            max_chars_per_doc: Character limit per document (ChatGPT: 1200)
            max_docs: Maximum documents to process (ChatGPT: 6)

        Returns:
            List of documents with compressed 'content'
        """
        logger.info(f"🔄 Extracting content from {len(documents)} documents for query")

        # Encode query once
        query_embedding = self.sentence_model.encode(query, convert_to_tensor=True)
        compressed_docs = []

        for doc_idx, doc in enumerate(documents[:max_docs]):
            content = doc.get('content', '')

            if len(content) <= max_chars_per_doc:
                # Document is already short enough
                logger.debug(f"  Doc {doc_idx+1}: {len(content)} chars - no compression needed")
                compressed_docs.append({
                    **doc,
                    'extraction_method': 'no_compression',
                    'original_length': len(content),
                    'compressed_length': len(content),
                    'compression_ratio': 1.0
                })
                continue

            # Step 1: Find outcome-related spans
            outcome_spans = self.find_outcome_spans(content)

            # Step 2: Extract text from these spans
            span_texts = []
            for start, end in outcome_spans:
                span_texts.append(content[start:end])

            # Step 3: Split into sentences for fine-grained ranking
            sentences = []
            sentence_positions = []

            for span_idx, span_text in enumerate(span_texts):
                # Simple sentence splitting (good enough for most cases)
                span_sentences = re.split(r'(?<=[.!?。！？])\s+', span_text)
                for sent in span_sentences:
                    sent = sent.strip()
                    if len(sent) > 20:  # Skip very short sentences
                        sentences.append(sent)
                        sentence_positions.append(span_idx)

            if not sentences:
                # Fallback to beginning
                logger.warning(f"  Doc {doc_idx+1}: No sentences found, using truncation")
                compressed_docs.append({
                    **doc,
                    'content': content[:max_chars_per_doc],
                    'extraction_method': 'truncation',
                    'original_length': len(content),
                    'compressed_length': max_chars_per_doc,
                    'compression_ratio': len(content) / max_chars_per_doc
                })
                continue

            # Step 4: Semantic ranking with MMR
            sentence_embeddings = self.sentence_model.encode(sentences, convert_to_tensor=True)
            sentence_embeddings_np = [emb.cpu().numpy() for emb in sentence_embeddings]
            query_embedding_np = query_embedding.cpu().numpy()

            # Apply MMR for diverse selection
            num_to_select = min(8, len(sentences))
            selected_indices = self.mmr_selection(
                query_embedding_np,
                sentence_embeddings_np,
                lambda_mult=0.7,
                k=num_to_select
            )

            # Step 5: Boost sentences with metrics
            boosted_indices = list(selected_indices)

            # Add metric-containing sentences not already selected
            for idx, sent in enumerate(sentences):
                if idx not in boosted_indices and self.contains_metrics(sent):
                    boosted_indices.append(idx)
                    if len(boosted_indices) >= 12:  # Limit total sentences
                        break

            # Step 6: Sort by original position to maintain context flow
            boosted_indices = sorted(set(boosted_indices))

            # Step 7: Reconstruct text up to char limit
            selected_text = []
            current_length = 0

            for idx in boosted_indices:
                sent = sentences[idx]
                sent_with_space = sent + ' '
                if current_length + len(sent_with_space) <= max_chars_per_doc:
                    selected_text.append(sent)
                    current_length += len(sent_with_space)
                else:
                    # Try to fit remaining space
                    remaining = max_chars_per_doc - current_length
                    if remaining > 50:  # Only add if we can fit meaningful text
                        selected_text.append(sent[:remaining-3] + '...')
                    break

            compressed_content = ' '.join(selected_text)

            # Step 8: Add metadata
            compression_ratio = len(content) / max(len(compressed_content), 1)

            logger.debug(
                f"  Doc {doc_idx+1}: {len(content)} → {len(compressed_content)} chars "
                f"({compression_ratio:.1f}x compression)"
            )

            compressed_docs.append({
                **doc,
                'content': compressed_content,
                'original_length': len(content),
                'compressed_length': len(compressed_content),
                'compression_ratio': compression_ratio,
                'extraction_method': 'semantic_mmr',
                'selected_sentences': len(selected_text),
                'outcome_spans_found': len(outcome_spans)
            })

        total_original = sum(d.get('original_length', len(d['content'])) for d in compressed_docs)
        total_compressed = sum(len(d['content']) for d in compressed_docs)
        overall_ratio = total_original / max(total_compressed, 1)

        logger.info(
            f"✅ Content extraction complete: {total_original} → {total_compressed} chars "
            f"({overall_ratio:.1f}x compression)"
        )

        return compressed_docs
