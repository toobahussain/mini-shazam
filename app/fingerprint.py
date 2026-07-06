"""
Audio fingerprinting core.

Pipeline:
  audio samples -> spectrogram (STFT) -> local peaks -> hashed peak-pairs

This follows the same idea as the original Shazam paper (Avery Wang, 2003):
pair up nearby frequency peaks and hash (freq1, freq2, time_delta) into a
single integer. These hashes are what gets stored in / looked up from Postgres.
"""

import hashlib
import numpy as np
import librosa
from scipy.ndimage import maximum_filter

# --- Tunable parameters -----------------------------------------------------

SAMPLE_RATE = 22050          # downsample audio to this rate (mono)
WINDOW_SIZE = 4096           # samples per FFT window
HOP_SIZE = 1024              # samples between successive windows (overlap)
PEAK_NEIGHBORHOOD = 20       # size of the local-max window when finding peaks
AMP_MIN = 10                 # minimum amplitude (dB-ish) for a peak to count
FAN_VALUE = 15               # how many neighboring peaks to pair each peak with
MIN_TIME_DELTA = 0           # ignore pairs closer than this (frames)
MAX_TIME_DELTA = 200         # ignore pairs farther than this (frames)


def load_audio(path: str) -> np.ndarray:
    """Load an audio file as mono float32 samples at SAMPLE_RATE."""
    y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    return y


def spectrogram(y: np.ndarray) -> np.ndarray:
    """Compute a magnitude spectrogram (frequency x time)."""
    S = librosa.stft(y, n_fft=WINDOW_SIZE, hop_length=HOP_SIZE)
    return np.abs(S)


def find_peaks(S: np.ndarray):
    """
    Find local maxima in the spectrogram that are also above an amplitude
    threshold. Returns a list of (freq_bin, time_frame) tuples.
    """
    # Work in log scale so louder AND quieter passages both yield usable peaks
    S_db = librosa.amplitude_to_db(S, ref=np.max)

    local_max = maximum_filter(S_db, size=PEAK_NEIGHBORHOOD) == S_db
    above_threshold = S_db > AMP_MIN + S_db.min()  # relative threshold

    peak_mask = local_max & above_threshold
    freq_bins, time_frames = np.where(peak_mask)

    return list(zip(freq_bins, time_frames))


def generate_hashes(peaks):
    """
    Pair each peak with nearby peaks that come after it in time, and hash
    (freq1, freq2, time_delta) into a single integer. Yields (hash, offset)
    where offset is the time frame of the FIRST peak in the pair -- this is
    what lets us later check that many hashes agree on the same alignment.
    """
    # Sort by time so pairing "future" peaks is straightforward
    peaks = sorted(peaks, key=lambda p: p[1])

    for i, (f1, t1) in enumerate(peaks):
        for j in range(1, FAN_VALUE):
            if i + j >= len(peaks):
                break
            f2, t2 = peaks[i + j]
            dt = t2 - t1
            if MIN_TIME_DELTA <= dt <= MAX_TIME_DELTA:
                h = _hash_pair(f1, f2, dt)
                yield h, t1


def _hash_pair(f1: int, f2: int, dt: int) -> int:
    """Pack (freq1, freq2, delta_t) into a single positive integer hash."""
    raw = f"{f1}|{f2}|{dt}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:16]  # 64 bits of the sha1
    return int(digest, 16) & 0x7FFFFFFFFFFFFFFF   # keep it a positive BIGINT


def fingerprint_file(path: str):
    """
    Full pipeline for one audio file.
    Returns a list of (hash, offset_time_seconds) tuples.
    """
    y = load_audio(path)
    S = spectrogram(y)
    peaks = find_peaks(S)
    hashes = list(generate_hashes(peaks))

    frames_per_second = SAMPLE_RATE / HOP_SIZE
    return [(h, offset_frame / frames_per_second) for h, offset_frame in hashes]


def fingerprint_bytes(audio_bytes: bytes, suffix: str = ".wav"):
    """Fingerprint raw audio bytes (e.g. an uploaded clip) by writing to a temp file."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return fingerprint_file(tmp_path)
    finally:
        os.remove(tmp_path)
