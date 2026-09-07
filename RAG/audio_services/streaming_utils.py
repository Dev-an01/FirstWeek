"""
Audio Streaming Utilities

Helper functions for sentence-by-sentence audio streaming optimization.
"""

import re
from typing import Tuple, List


def has_complete_sentence(text: str, min_length: int = 30) -> bool:
    """
    Check if text contains at least one complete sentence.

    Args:
        text: Text to check
        min_length: Minimum length to consider a valid sentence

    Returns:
        True if text contains a complete sentence
    """
    # Match sentence endings: . ! ? (English) and 。！？ (Japanese) followed by space, newline, or end of string
    sentence_endings = re.search(r'[.!?。！？](\s|$)', text)
    return sentence_endings is not None and len(text.strip()) >= min_length


def extract_first_sentence(text: str) -> Tuple[str, str]:
    """
    Extract the first complete sentence from text.

    Args:
        text: Text containing one or more sentences

    Returns:
        Tuple of (first_sentence, remaining_text)
    """
    # Find first sentence ending (English: .!? or Japanese: 。！？)
    match = re.search(r'[.!?。！？](\s|$)', text)

    if match:
        # Extract sentence including the punctuation
        end_pos = match.end()
        sentence = text[:end_pos].strip()
        remaining = text[end_pos:].strip()
        return sentence, remaining

    # No sentence ending found, return all text
    return text.strip(), ""


def extract_all_sentences(text: str) -> List[str]:
    """
    Extract all complete sentences from text.

    Args:
        text: Text containing multiple sentences

    Returns:
        List of sentences
    """
    sentences = []
    remaining = text

    while remaining:
        if has_complete_sentence(remaining):
            sentence, remaining = extract_first_sentence(remaining)
            if sentence:
                sentences.append(sentence)
        else:
            # No more complete sentences
            if remaining.strip():
                sentences.append(remaining.strip())
            break

    return sentences


def clean_text_for_tts(text: str) -> str:
    """
    Clean text for TTS processing.

    Removes:
    - All square bracket content (e.g., [Source: ...], [Core Value: ...])
    - Emojis
    - Markdown formatting
    - Special characters that get pronounced

    Args:
        text: Raw text with markdown/citations/emojis

    Returns:
        Cleaned text suitable for TTS
    """
    # Remove ALL content in square brackets (citations, sources, metadata, etc.)
    text = re.sub(r'\s*\[[^\]]+\]\s*', ' ', text)

    # Remove markdown formatting
    text = text.replace('**', '')  # Bold
    text = text.replace('__', '')  # Underline
    text = text.replace('~~', '')  # Strikethrough
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links [text](url) -> text

    # Remove emojis (Unicode emoji ranges)
    # Carefully exclude CJK (Chinese/Japanese/Korean) character ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U0000FE00-\U0000FE0F"  # Variation Selectors
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)

    # Note: We do NOT include ranges that contain CJK characters:
    # - \U00003000-\U0000303F (CJK Symbols and Punctuation)
    # - \U00004E00-\U00009FFF (CJK Unified Ideographs)
    # - \U00003040-\U0000309F (Hiragana)
    # - \U000030A0-\U000030FF (Katakana)

    # Remove multiple punctuation marks in a row (e.g., "!!!" -> "!")
    text = re.sub(r'([!?.])\1+', r'\1', text)

    # Remove standalone colons that might be pronounced
    # Keep colons in times (e.g., 10:30) but remove standalone ones
    text = re.sub(r'\s+:\s+', ' ', text)  # " : " -> " "
    text = re.sub(r'\s+:$', '', text)      # Trailing colons

    # Remove spaces before punctuation (caused by removing emojis/citations)
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    return text.strip()


def should_start_tts(sentence_buffer: str, streaming_mode: str) -> bool:
    """
    Determine if TTS should start based on streaming mode and buffer.

    Args:
        sentence_buffer: Current sentence buffer
        streaming_mode: Streaming mode (immediate, buffered, sentence)

    Returns:
        True if TTS should start now
    """
    if streaming_mode == "immediate":
        # Start TTS as soon as we have a complete sentence
        return has_complete_sentence(sentence_buffer, min_length=20)

    elif streaming_mode == "sentence":
        # Start TTS with slightly longer sentences
        return has_complete_sentence(sentence_buffer, min_length=40)

    elif streaming_mode == "buffered":
        # For buffered mode, accumulate more text (handled separately with AudioQueue)
        return False

    return False
