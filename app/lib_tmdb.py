import os
import requests
import unicodedata
import re

BASE_URL = "https://api.themoviedb.org/3"

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY not set in environment")


# ---------- Name helpers (for optional director disambiguation) ----------

def _normalize_name(name: str) -> str:
    name = name.strip().lower()
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _last_name(name: str) -> str | None:
    norm = _normalize_name(name)
    if not norm:
        return None
    tokens = norm.split()
    return tokens[-1] if tokens else None


# ---------- STEP 1: Find the movie (once) and get its ID ----------

def tmdb_find_movie(title: str,
                    director: str | None = None,
                    language: str = "en-US",
                    max_candidates: int = 10) -> dict | None:
    """
    Search TMDb by title, optionally disambiguate by director last name.
    Returns a TMDb movie dict or None if nothing is found.
    """

    title = (title or "").strip()
    if not title:
        return None

    resp = requests.get(
        f"{BASE_URL}/search/movie",
        params={
            "api_key": TMDB_API_KEY,
            "query": title,
            "language": language,
            "include_adult": False,
            "page": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    if not results:
        return None

    # No director provided -> just use best title match
    if not director:
        return results[0]

    target_last = _last_name(director)
    if not target_last:
        return results[0]

    # Try to find a candidate whose director last name matches
    for movie in results[:max_candidates]:
        movie_id = movie["id"]
        credits_resp = requests.get(
            f"{BASE_URL}/movie/{movie_id}/credits",
            params={"api_key": TMDB_API_KEY},
            timeout=10,
        )
        credits_resp.raise_for_status()
        crew = credits_resp.json().get("crew", [])
        directors_here = [p["name"] for p in crew if p.get("job") == "Director"]

        for cand in directors_here:
            cand_last = _last_name(cand)
            if cand_last and cand_last == target_last:
                return movie

    # No director match -> fall back to first result
    return results[0]


def tmdb_get_movie_id(title: str,
                      director: str | None = None,
                      language: str = "en-US") -> int | None:
    """
    Convenience: returns only the TMDb movie ID.
    """
    movie = tmdb_find_movie(title, director=director, language=language)
    return movie["id"] if movie else None


# ---------- STEP 2: ID-based detail queries ----------

def tmdb_get_movie_details(movie_id: int) -> dict:
    """Core movie metadata: title, overview, runtime, genres, etc."""
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}",
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def tmdb_get_movie_credits(movie_id: int) -> dict:
    """Cast and crew."""
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}/credits",
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def tmdb_get_movie_images(movie_id: int) -> dict:
    """Posters, backdrops, logos."""
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}/images",
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def tmdb_get_movie_videos(movie_id: int) -> dict:
    """Trailers, teasers, clips, etc."""
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}/videos",
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def tmdb_poster_url_from_id(movie_id: int, size: str = "w342") -> str | None:
    """
    Get a poster URL for a given movie ID.
    `size` can be: w92, w154, w185, w342, w500, w780, original.
    """
    details = tmdb_get_movie_details(movie_id)
    poster_path = details.get("poster_path")
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"

def pick_best_poster(images: dict) -> dict | None:
    """
    Given data from /movie/{id}/images, return the single
    'best' poster based purely on use/popularity, regardless of language.

    Ranking priority:
      1) vote_count (descending)
      2) vote_average (descending)
      3) area = width * height (descending)
    """
    posters = images.get("posters", [])
    if not posters:
        return None

    def score(p):
        vc = p.get("vote_count") or 0
        va = p.get("vote_average") or 0.0
        w = p.get("width") or 0
        h = p.get("height") or 0
        return (vc, va, w * h)

    posters.sort(key=score, reverse=True)
    return posters[0]

def tmdb_poster_url_from_poster_dict(poster: dict, size="w342") -> str | None:
    if not poster:
        return None
    
    file_path = poster.get("file_path")
    if not file_path:
        return None
    
    return f"https://image.tmdb.org/t/p/{size}{file_path}"

def tmdb_get_trailer_url(movie_id: int) -> str | None:
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}/videos",
        params={"api_key": TMDB_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None

    # Prefer: Official → Trailer → YouTube
    def score(v):
        return (
            (v.get("official") is True),
            v.get("type") == "Trailer",
            v.get("site") == "YouTube",
            v.get("published_at") or "",
        )

    results.sort(key=score, reverse=True)

    best = results[0]
    if best.get("site") == "YouTube" and best.get("key"):
        return f"https://www.youtube.com/watch?v={best['key']}"

    # fallback for non-YouTube (rare)
    if best.get("url"):
        return best["url"]

    return None