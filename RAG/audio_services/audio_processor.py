"""
Audio Processing Module

Converts raw audio to standardized PCM frames for WebRTC compatibility.
Handles audio format validation, frame conversion, and buffer management.
"""

import logging
import struct
from typing import List, Tuple, Optional
import numpy as np

from .config import AUDIO_SPECS

logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    """Base exception for audio processing errors"""
    pass


class AudioFormatError(AudioProcessingError):
    """Raised when audio format is invalid"""
    pass


class AudioProcessor:
    """
    Processes raw audio into standardized PCM frames.

    Converts variable-sized audio chunks into fixed-size frames
    of exactly 441 samples (20ms @ 22.05kHz) for WebRTC compatibility.

    Features:
    - Validates audio format (sample rate, bit depth, channels)
    - Converts variable chunks to fixed 441-sample frames
    - Buffers incomplete frames across chunks
    - Zero audio loss through proper buffering
    """

    def __init__(
        self,
        sample_rate: Optional[int] = None,
        bit_depth: Optional[int] = None,
        channels: Optional[int] = None
    ):
        """
        Initialize audio processor.

        Args:
            sample_rate: Audio sample rate (default from AUDIO_SPECS: 22050)
            bit_depth: Bit depth (default from AUDIO_SPECS: 16)
            channels: Number of channels (default from AUDIO_SPECS: 1)
        """
        self.sample_rate = sample_rate or AUDIO_SPECS['sample_rate']
        self.bit_depth = bit_depth or AUDIO_SPECS['bit_depth']
        self.channels = channels or AUDIO_SPECS['channels']
        self.frame_size = AUDIO_SPECS['frame_size']  # 441 samples
        self.frame_duration_ms = AUDIO_SPECS['frame_duration_ms']  # 20ms

        self.bytes_per_sample = self.bit_depth // 8
        self.bytes_per_frame = self.frame_size * self.bytes_per_sample

        # Buffer for incomplete frames
        self.buffer = bytearray()

        logger.info(f"AudioProcessor initialized:")
        logger.info(f"  Sample rate: {self.sample_rate} Hz")
        logger.info(f"  Bit depth: {self.bit_depth}-bit")
        logger.info(f"  Channels: {self.channels}")
        logger.info(f"  Frame size: {self.frame_size} samples ({self.bytes_per_frame} bytes)")

    def validate_format(
        self,
        sample_rate: int,
        bit_depth: int,
        channels: int
    ) -> bool:
        """
        Validate audio format matches expected specifications.

        Args:
            sample_rate: Audio sample rate
            bit_depth: Bit depth (e.g., 16)
            channels: Number of channels (1 for mono, 2 for stereo)

        Returns:
            True if format is valid

        Raises:
            AudioFormatError: If format doesn't match specifications
        """
        tolerance = AUDIO_SPECS['sample_rate_tolerance']
        expected_sr = self.sample_rate
        sr_diff = abs(sample_rate - expected_sr) / expected_sr

        if sr_diff > tolerance:
            raise AudioFormatError(
                f"Sample rate {sample_rate} Hz doesn't match expected "
                f"{expected_sr} Hz (tolerance: {tolerance * 100}%)"
            )

        if bit_depth != self.bit_depth:
            raise AudioFormatError(
                f"Bit depth {bit_depth} doesn't match expected {self.bit_depth}"
            )

        if channels != self.channels:
            raise AudioFormatError(
                f"Channels {channels} doesn't match expected {self.channels}"
            )

        return True

    def process_chunk(self, audio_chunk: bytes) -> List[bytes]:
        """
        Process audio chunk into standardized frames.

        Converts variable-sized audio chunks into fixed-size frames.
        Buffers incomplete frames for next chunk.

        Args:
            audio_chunk: Raw audio data (PCM16)

        Returns:
            List of audio frames (each frame is exactly 441 samples = 882 bytes)

        Example:
            processor = AudioProcessor()
            for chunk in audio_stream:
                frames = processor.process_chunk(chunk)
                for frame in frames:
                    # Send frame to WebSocket
                    send_frame(frame)
        """
        # Add to buffer
        self.buffer.extend(audio_chunk)

        # Extract complete frames
        frames = []
        while len(self.buffer) >= self.bytes_per_frame:
            frame = bytes(self.buffer[:self.bytes_per_frame])
            frames.append(frame)
            self.buffer = self.buffer[self.bytes_per_frame:]

        return frames

    def flush_remaining(self, pad: bool = True) -> Optional[bytes]:
        """
        Flush remaining buffered audio as a final frame.

        Args:
            pad: If True, pad incomplete frame with zeros

        Returns:
            Final frame (padded if necessary) or None if buffer empty
        """
        if len(self.buffer) == 0:
            return None

        if pad:
            # Pad with zeros to complete frame
            padding_needed = self.bytes_per_frame - len(self.buffer)
            self.buffer.extend(b'\x00' * padding_needed)

        frame = bytes(self.buffer)
        self.buffer = bytearray()

        return frame

    def clear_buffer(self):
        """Clear internal buffer (e.g., on stream reset)"""
        self.buffer = bytearray()

    def get_buffer_size(self) -> int:
        """Get current buffer size in bytes"""
        return len(self.buffer)

    def bytes_to_samples(self, audio_bytes: bytes) -> np.ndarray:
        """
        Convert PCM bytes to numpy array of samples.

        Args:
            audio_bytes: Raw PCM audio bytes

        Returns:
            Numpy array of audio samples (float32, normalized to [-1, 1])
        """
        if self.bit_depth == 16:
            # Unpack 16-bit PCM
            samples = np.frombuffer(audio_bytes, dtype=np.int16)
            # Normalize to [-1, 1]
            return samples.astype(np.float32) / 32768.0
        else:
            raise AudioProcessingError(f"Unsupported bit depth: {self.bit_depth}")

    def samples_to_bytes(self, samples: np.ndarray) -> bytes:
        """
        Convert numpy array of samples to PCM bytes.

        Args:
            samples: Numpy array of audio samples (float32, range [-1, 1])

        Returns:
            Raw PCM audio bytes
        """
        if self.bit_depth == 16:
            # Denormalize and convert to int16
            int_samples = (samples * 32768.0).astype(np.int16)
            return int_samples.tobytes()
        else:
            raise AudioProcessingError(f"Unsupported bit depth: {self.bit_depth}")

    def resample(
        self,
        audio_bytes: bytes,
        source_sample_rate: int,
        target_sample_rate: Optional[int] = None
    ) -> bytes:
        """
        Resample audio to target sample rate.

        Args:
            audio_bytes: Raw PCM audio bytes
            source_sample_rate: Original sample rate
            target_sample_rate: Target sample rate (default: self.sample_rate)

        Returns:
            Resampled audio bytes

        Note:
            Requires scipy for resampling. This is a placeholder for future use.
        """
        target_sr = target_sample_rate or self.sample_rate

        if source_sample_rate == target_sr:
            return audio_bytes

        # Convert to samples
        samples = self.bytes_to_samples(audio_bytes)

        # Resample (requires scipy)
        try:
            from scipy import signal
            num_samples = int(len(samples) * target_sr / source_sample_rate)
            resampled = signal.resample(samples, num_samples)
            return self.samples_to_bytes(resampled)
        except ImportError:
            raise AudioProcessingError(
                "scipy required for resampling. Install with: pip install scipy"
            )

    def get_info(self) -> dict:
        """Get audio processor information"""
        return {
            'sample_rate': self.sample_rate,
            'bit_depth': self.bit_depth,
            'channels': self.channels,
            'frame_size': self.frame_size,
            'frame_duration_ms': self.frame_duration_ms,
            'bytes_per_frame': self.bytes_per_frame,
            'buffer_size': len(self.buffer),
        }
