from collections import defaultdict, Counter

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db, fingerprint

app = FastAPI(title="Mini Shazam")

# Allow the simple HTML frontend (served separately or via file://) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/add-song")
async def add_song(
    title: str = Form(...),
    artist: str = Form(""),
    file: UploadFile = File(...),
):
    """Upload a full song, fingerprint it, and store it in the database."""
    audio_bytes = await file.read()
    suffix = "." + file.filename.split(".")[-1] if "." in file.filename else ".wav"

    hashes = fingerprint.fingerprint_bytes(audio_bytes, suffix=suffix)
    song_id = db.add_song(title, artist)
    db.store_fingerprints(song_id, hashes)

    return {
        "song_id": song_id,
        "title": title,
        "artist": artist,
        "num_fingerprints": len(hashes),
    }


@app.post("/identify")
async def identify(file: UploadFile = File(...)):
    """Upload a short clip and try to identify which stored song it's from."""
    audio_bytes = await file.read()
    suffix = "." + file.filename.split(".")[-1] if "." in file.filename else ".wav"

    clip_hashes = fingerprint.fingerprint_bytes(audio_bytes, suffix=suffix)
    matches = db.lookup_hashes(clip_hashes)

    if not matches:
        return {"match": None, "reason": "no matching fingerprints found"}

    # Map hash -> clip_offset for quick lookup
    clip_offset_by_hash = dict(clip_hashes)

    # For each song, tally how often a particular (db_offset - clip_offset)
    # occurs. A real match has MANY hashes agreeing on the same delta;
    # random noise scatters across many different deltas.
    song_offset_votes = defaultdict(Counter)

    for hash_val, song_id, db_offset in matches:
        clip_offset = clip_offset_by_hash.get(hash_val)
        if clip_offset is None:
            continue
        delta = round(db_offset - clip_offset, 1)  # bucket to 0.1s to allow slight jitter
        song_offset_votes[song_id][delta] += 1

    # Score each song by its best-aligned offset's vote count
    scores = []
    for song_id, offset_counter in song_offset_votes.items():
        best_delta, best_count = offset_counter.most_common(1)[0]
        scores.append((song_id, best_count, best_delta))

    scores.sort(key=lambda x: x[1], reverse=True)
    best_song_id, confidence, offset = scores[0]

    song = db.get_song(best_song_id)
    if not song:
        return {"match": None, "reason": "matched song no longer exists"}

    return {
        "match": {
            "song_id": song[0],
            "title": song[1],
            "artist": song[2],
            "confidence_score": confidence,
            "matched_at_seconds": offset,
        },
        "runner_ups": [
            {"song_id": s, "confidence_score": c} for s, c, _ in scores[1:4]
        ],
    }


@app.get("/songs")
def songs():
    rows = db.list_songs()
    return [{"id": r[0], "title": r[1], "artist": r[2]} for r in rows]


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the simple frontend at /  (static/index.html)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
