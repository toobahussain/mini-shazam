# Mini Shazam

A small audio-fingerprinting song identifier: Python + FastAPI backend,
Postgres for fingerprint storage, plain HTML/JS frontend using the Web Audio API
to record from your mic.

## How it works
 
1. **Add songs**: each song is loaded, turned into a spectrogram, and reduced to
   a set of fingerprint hashes (pairs of frequency peaks + the time between them).
   These hashes are stored in Postgres.
2. **Identify a clip**: the recorded clip goes through the same fingerprinting
   process. Its hashes are looked up in the database. Whichever song has the most
   hashes agreeing on the *same time offset* wins — that consistent alignment is
   what makes this robust to background noise.

See `app/fingerprint.py` for the actual algorithm — it's commented step by step.

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`librosa` needs `ffmpeg`/`libsndfile` under the hood for some formats.
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: install ffmpeg and add it to PATH

### 2. Create the database

```bash
createdb shazam
psql -d shazam -f schema.sql
```

### 3. Configure the connection

```bash
cp .env.example .env
# edit .env if your Postgres user/password/host/db name differ
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000** — the frontend is served automatically.

## Using it

1. Go to **Add a song to the library**, give it a title, pick an MP3/WAV file, click **Add to library**.
   Do this for a handful of songs (fingerprinting takes a few seconds per song).
2. Click **Listen (10s)** and play/hum/sing part of one of those songs near your mic.
3. It'll show which song matched, at what timestamp, and a confidence score.

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/add-song` | POST (form: `title`, `artist`, `file`) | Fingerprint + store a song |
| `/identify` | POST (form: `file`) | Identify a short audio clip |
| `/songs` | GET | List all songs in the library |
| `/health` | GET | Health check |

## Tuning / next steps

- `app/fingerprint.py` has constants at the top (`FAN_VALUE`, `AMP_MIN`, etc.) —
  raise `AMP_MIN` for fewer/stronger fingerprints, raise `FAN_VALUE` for more
  hash pairs per peak (slower fingerprinting, but better matching on noisy clips).
- For a bigger library, consider batching hash inserts and adding a composite
  index; Postgres will comfortably handle millions of fingerprint rows as-is.
- For a real mobile app, keep this backend as-is and build a thin React Native /
  Flutter client that just records audio and POSTs to `/identify`.
