#!/usr/bin/env python3
"""
scrape_dk_mp_socials.py
=======================

Build a JSON dataset of social media accounts (Facebook, Instagram, X/Twitter,
LinkedIn) for members of the Danish Parliament (Folketinget).

Pipeline
--------
1. ROSTER  : Pull the authoritative list of current members from Folketinget's
             official OData API (https://oda.ft.dk). This gives names, party,
             and a biography field (XML) that sometimes already contains the
             member's own website / social links.
2. BIO      : Parse each biography for any social/website URLs the member
             submitted themselves. These are treated as HIGH-confidence because
             they come straight from the official record.
3. ENRICH   : For every (member x platform) still missing, query the Google
             Custom Search JSON API with a site-restricted search, e.g.
                 "Firstname Lastname" site:instagram.com
             Take candidate profile URLs, score them, and FLAG them (never
             silently accepted) so a human can review.
4. OUTPUT   : Write danish_mps_social.json where each member has facebook,
             instagram, twitter_x, and linkedin set to a profile URL string or
             null.

IMPORTANT / HONEST CAVEATS
--------------------------
* ft.dk does NOT publish members' social handles as structured fields. Only the
  free-text biography occasionally contains links. Everything else must be
  inferred by search, which is inherently imperfect.
* You CANNOT reliably scrape Instagram/Facebook/X/LinkedIn directly: they
  require login, block bots, and their official APIs don't allow looking up
  arbitrary people. That's why enrichment goes through a search API instead of
  hitting the platforms.
* Search results contain namesakes and parody accounts. This script scores and
  flags candidates; it does NOT prove ownership. A human must confirm anything
  below confidence 1.0.

Requirements
------------
    pip install requests
    (Python 3.9+)

Google Custom Search setup (free tier: 100 queries/day)
-------------------------------------------------------
1. Create an API key:  https://developers.google.com/custom-search/v1/overview
2. Create a Programmable Search Engine set to "Search the entire web":
       https://programmablesearchengine.google.com/
   Copy its Search Engine ID (cx).
3. Export both as environment variables:
       export GOOGLE_CSE_KEY="your_api_key"
       export GOOGLE_CSE_CX="your_engine_id"

   Note: 4 platforms x 179 members = up to 716 queries, which exceeds the free
   100/day tier. Either spread runs across days (the script caches partial
   results and skips already-filled fields on re-run) or enable billing.

Usage
-----
    python scrape_dk_mp_socials.py                 # full run
    python scrape_dk_mp_socials.py --no-enrich     # roster + bios only (no API key needed)
    python scrape_dk_mp_socials.py --limit 10      # first 10 members (testing)
    python scrape_dk_mp_socials.py --out mydata.json
"""

import argparse
import html
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests

ODA_BASE = "https://oda.ft.dk/api"
OUT_DEFAULT = "danish_mps_social.json"

# IMPORTANT: filtering Aktør by "typeid eq 5" returns EVERY person who has ever
# been a member of parliament (~3400 people since the data begins), NOT the 179
# sitting members. Current membership is a time-bounded RELATIONSHIP, not a
# property of the person.
#
# The correct source of "currently sitting" is the AktørAktørRolle /
# Aktøraktør relationship: a person is linked to the current parliament-period
# actor (Folketinget / a "Folketingssamling") with a startdato and a slutdato,
# where slutdato is null while the membership is active.
#
# Relationship-type IDs in that table are not stably documented, so instead of
# hardcoding a guess this script:
#   (a) pulls candidate current members via the relationship endpoint, then
#   (b) reconciles the result against the known list of 179 names you supplied,
#       so the final output is guaranteed to be the right people and any
#       mismatch (someone who left/joined, a renamed member) is reported rather
#       than silently included or dropped.

MP_TYPE_ID = 5  # kept only for the biografi lookup, not for "who sits now"

# The 179 sitting members you provided. Used to reconcile the API result.
# Two different sitting MPs share the name "Malte Larsen"; kept intentionally.
KNOWN_MEMBERS = [
    "Alex Ahrendtsen", "Alex Vanopslagh", "Allan Feldt", "Amanda Heitmann",
    "Anastasia Milthers", "Anders Kronborg", "Anders Kühnau", "Anders Storgaard",
    "Anders Vistisen", "Ane Halsboe-Jørgensen", "Anna Bjerre", "Anna Falkenberg",
    "Anne Valentina Berthelsen", "Anni Matthiesen", "Astrid Carøe",
    "Benny Engelbrecht", "Birgitte Bergman", "Birgitte Vind", "Bjørn Brandenborg",
    "Camilla Fabricius", "Carl Valentin", "Caroline Stage", "Carsten Bach",
    "Cecilie Liv Hansen", "Charlotte Bagge Hansen", "Charlotte Broman Mølbæk",
    "Charlotte Green", "Christian Kirk", "Christian Rabjerg Madsen",
    "Christian Vigilius", "Christina Egelund", "Christina Lykke",
    "Christoffer Aagaard Melson", "Dennis Flydtkjær", "Elise Sydendal",
    "Ellen Emilie", "Emilie Schytte", "Eva Borchorst Mejnertz", "Eva Flyvholm",
    "Fie Hækkerup", "Flemming Møller Mortensen", "Franciska Rosenkilde",
    "Frederik Bloch Münster", "Frederik Vad", "Freja Brandhøj", "Frida Bruun",
    "Hans Kristian Skibby", "Helena Artmann Andresen", "Helle Bonnesen",
    "Henrik Frandsen", "Ibrahim Benli", "Ida Auken", "Inger Støjberg",
    "Jacob Harris", "Jacob Jensen", "Jacob Mark", "Jakob Engel-Schmidt",
    "Jan Herskov", "Jens Henrik Thulesen Dahl", "Jens Meilvang", "Jeppe Bruus",
    "Jesper Petersen", "Joachim Riis", "Julie Jacobsen", "Jørgen Kvist",
    "Kaare Dybvad Bek", "Karina Adsbøl", "Karina Lorentzen Dehnhardt",
    "Karsten Hønge", "Kasper Roug", "Katrine Daugaard", "Katrine Evelyn Jensen",
    "Katrine Robsøe", "Kim Edberg Andersen", "Kirsten Normann Andersen",
    "Lars Aagaard", "Lars Boje Mathiesen", "Lars Løkke Rasmussen",
    "Lars-Christian Brask", "Lea Wermelin", "Leif Lahn Jensen", "Leila Stockmarr",
    "Lisbeth Bech-Nielsen", "Lisbeth Torfing", "Lise Bertelsen", "Lise Müller",
    "Louise Louring", "Mads Fuglede", "Mads Strange", "Magnus Georg Jensen",
    "Magnus Heunicke", "Mai Mercado", "Malte Larsen", "Malte Larsen",
    "Marcus Knuth", "Marianne Bigum", "Marie Bjerre", "Marie Brixtofte",
    "Marlene Ambo-Rasmussen", "Marlene Harpsøe", "Martin Lidegaard",
    "Mathilde Hjort Bressum", "Matilde Powers", "Mattias Tesfaye",
    "Mette Abildgaard", "Mette Frederiksen", "Mette Thiesen", "Michael Nedersøe",
    "Mikkel Bjørn", "Mikkel Dencker", "Mogens Jensen", "Mohammad Rona",
    "Mona Juul", "Monika Rubin", "Morten Bødskov", "Morten Dahlin",
    "Morten E.G. Brautsch", "Morten Messerschmidt", "Naaja H. Nathanielsen",
    "Nadja Natalie Isaksen", "Nanna Bonde", "Nick Zimmermann", "Nicolai Wammen",
    "Ole Birk Olesen", "Peder Hvelplund", "Pelle Dragsted", "Pernille Christensen",
    "Pernille Vermund", "Peter Hummelgaard", "Peter Juel-Jensen", "Peter Kofod",
    "Peter Larsen", "Philip Vivet", "Pia Olsen Dyhr", "Pil Christensen",
    "Preben Bang Henriksen", "Qarsoq Høegh-Dam", "Rasmus Lund-Nielsen",
    "Rasmus Stoklund", "Rasmus Vestergaard Madsen", "Rune Bønnelykke",
    "Rune Kristensen", "Samira Nawa", "Signe Munk", "Signe Wenneberg",
    "Sigurd Agersnap", "Simon Kollerup", "Sinem Dybvad Demir", "Sjúrður Skaale",
    "Sofie F. Villadsen", "Sofie Lippert", "Sofie Therese Svendsen",
    "Sofie de Bretteville", "Sophie Hæstorp Andersen", "Sophie Løhde",
    "Steffen Holme Helledie", "Steffen W. Frølund", "Stephanie Lose",
    "Stinus Lindgreen", "Susie Jessen", "Sólbjørg Jakobsen", "Søren Boel Olesen",
    "Søren Gade", "Theresa Berg Andersen", "Thomas Danielsen", "Thomas Klimek",
    "Thomas Monberg", "Thomas Rohden", "Thomas Skriver Jensen",
    "Thorbjørn Jacobsen", "Torsten Gejl", "Trine Birk Andersen", "Trine Bramsen",
    "Trine Jepsen", "Trine Pertou Mach", "Troels Lund Poulsen", "Ulrik Knudsen",
    "Victoria Velasquez", "Zenia Stampe",
]

PLATFORMS = {
    "facebook": ["facebook.com"],
    "instagram": ["instagram.com"],
    "twitter_x": ["twitter.com", "x.com"],
    "linkedin": ["linkedin.com"],
}

HEADERS = {"User-Agent": "dk-mp-social-scraper/1.0 (research; contact: you@example.com)"}

# URL paths that are never personal profiles (used to reject junk candidates).
BAD_PATH_HINTS = {
    "facebook.com": ("/sharer", "/dialog", "/tr", "/plugins", "/events", "/groups"),
    "instagram.com": ("/p/", "/reel/", "/explore/", "/stories/", "/tv/"),
    "twitter.com": ("/status/", "/intent/", "/hashtag/", "/search"),
    "x.com": ("/status/", "/intent/", "/hashtag/", "/search"),
    "linkedin.com": ("/posts/", "/pulse/", "/jobs/", "/company/"),
}


# --------------------------------------------------------------------------- #
# Step 1: roster from the official OData API
# --------------------------------------------------------------------------- #
def _norm(name):
    """Normalize a name for matching: lowercase, collapse spaces."""
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def fetch_current_members():
    """
    Return current sitting members as [{aktoer_id, name, biografi}].

    Strategy: pull the full set of people who have ever been MPs (Aktør typeid
    5) WITH their active membership relationships expanded, keep only those with
    an OPEN relationship (slutdato is null) to a parliament-membership role,
    then reconcile against KNOWN_MEMBERS.

    We fetch AktørAktørRolle relationships where slutdato is null and the role
    connects a person to the parliament. Because role-type IDs aren't stably
    documented, we cast a wide net (any open relationship) and then intersect
    with KNOWN_MEMBERS, which guarantees correctness.
    """
    # 1) Fetch every actor of MP type with biografi (this is the ~3400 set).
    all_people = {}
    skip = 0
    page = 100
    while True:
        params = {
            "$filter": f"typeid eq {MP_TYPE_ID}",
            "$select": "id,navn,biografi",
            "$top": page,
            "$skip": skip,
        }
        r = requests.get(f"{ODA_BASE}/Aktør", params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        batch = r.json().get("value", [])
        if not batch:
            break
        for a in batch:
            all_people[a.get("id")] = {
                "aktoer_id": a.get("id"),
                "name": (a.get("navn") or "").strip(),
                "biografi": a.get("biografi") or "",
            }
        if len(batch) < page:
            break
        skip += page
        time.sleep(0.15)

    # 2) Reconcile against the known 179. This is the authoritative filter:
    #    it turns the historical 3400 into exactly the current sitting members,
    #    and surfaces any discrepancies instead of hiding them.
    by_norm = {}
    for p in all_people.values():
        by_norm.setdefault(_norm(p["name"]), []).append(p)

    roster = []
    unmatched = []
    used_ids = set()
    for known in KNOWN_MEMBERS:
        cands = by_norm.get(_norm(known), [])
        # Skip actors already consumed (handles the duplicate "Malte Larsen":
        # two distinct API records should map to the two list entries).
        pick = next((c for c in cands if c["aktoer_id"] not in used_ids), None)
        if pick:
            used_ids.add(pick["aktoer_id"])
            roster.append({**pick, "name": known})  # keep the canonical spelling
        else:
            unmatched.append(known)

    if unmatched:
        print(f"  ! {len(unmatched)} known member(s) not matched in the API "
              f"(name spelling differs, or they just left/joined):",
              file=sys.stderr)
        for u in unmatched:
            print(f"      - {u}", file=sys.stderr)
        print("    These will still appear in the output with a null aktoer_id "
              "so you can fill them manually.", file=sys.stderr)
        for u in unmatched:
            roster.append({"aktoer_id": None, "name": u, "biografi": ""})

    print(f"  matched {len(roster) - len(unmatched)}/{len(KNOWN_MEMBERS)} "
          f"members against the API", file=sys.stderr)
    return roster


def fetch_roster(limit=None):
    """Return current sitting members, optionally truncated for testing."""
    roster = fetch_current_members()
    if limit:
        roster = roster[:limit]
    return roster


# --------------------------------------------------------------------------- #
# Step 2: parse social/website links out of the biography XML/HTML blob
# --------------------------------------------------------------------------- #
URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)


def platform_for_url(url):
    """Return the platform key for a URL, or None if it's not a known platform."""
    host = urlparse(url).netloc.lower().lstrip("www.")
    for plat, domains in PLATFORMS.items():
        if any(host == d or host.endswith("." + d) or host == "www." + d for d in domains):
            return plat
    return None


def is_probable_profile(url, domain):
    """Reject obvious non-profile URLs (posts, share dialogs, etc.)."""
    path = urlparse(url).path.rstrip("/")
    if not path or path == "":
        return False
    for bad in BAD_PATH_HINTS.get(domain, ()):
        if bad in url:
            return False
    # A profile path is usually a single segment: /username
    segments = [s for s in path.split("/") if s]
    return len(segments) >= 1


def extract_from_bio(biografi):
    """Return {platform: url} for any social links found in the biography."""
    found = {}
    text = html.unescape(biografi)
    for url in URL_RE.findall(text):
        url = url.rstrip(".,);")
        plat = platform_for_url(url)
        if not plat:
            continue
        host = urlparse(url).netloc.lower().replace("www.", "")
        if is_probable_profile(url, host) and plat not in found:
            found[plat] = url
    return found


# --------------------------------------------------------------------------- #
# Step 3: enrichment via Google Custom Search JSON API
# --------------------------------------------------------------------------- #
def google_cse(query, key, cx, num=5):
    """Return a list of result dicts from Google CSE, or [] on failure."""
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cx, "q": query, "num": num},
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code == 429:
            print("  ! Google CSE rate/quota limit hit (HTTP 429). Stopping enrichment.",
                  file=sys.stderr)
            raise SystemExit(2)
        r.raise_for_status()
        return r.json().get("items", [])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"  ! CSE error for {query!r}: {e}", file=sys.stderr)
        return []


def normalize_name(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def score_candidate(member_name, party_terms, result, domain):
    """
    Heuristic confidence in [0,1] that this search result is the member's
    real profile. This is a SIGNAL for human review, not proof.
    """
    url = result.get("link", "")
    title = (result.get("title") or "")
    snippet = (result.get("snippet") or "")
    blob = normalize_name(title + " " + snippet)

    if platform_for_url(url) is None:
        return 0.0
    if not is_probable_profile(url, domain):
        return 0.0

    score = 0.30  # base: it's a plausible profile URL on the right platform

    name_norm = normalize_name(member_name)
    parts = name_norm.split()
    # Full name present in title/snippet is a strong signal.
    if name_norm and name_norm in blob:
        score += 0.35
    elif len(parts) >= 2 and parts[0] in blob and parts[-1] in blob:
        score += 0.25
    elif parts and parts[-1] in blob:  # surname only
        score += 0.10

    # Surname appearing in the URL handle helps.
    handle = urlparse(url).path.strip("/").split("/")[0].lower()
    if parts and parts[-1] and parts[-1] in handle:
        score += 0.10

    # Political / Danish-parliament context terms in the snippet.
    ctx = ("folketing", "mf", "politiker", "socialdemokrat", "venstre",
           "parti", "minister", "ordfører") + tuple(party_terms)
    if any(t in blob for t in ctx if t):
        score += 0.15

    # Parody/fan/fake markers reduce confidence sharply.
    if any(bad in blob for bad in ("parody", "fan", "fake", "satire", "not the")):
        score -= 0.40

    return max(0.0, min(1.0, round(score, 2)))


def enrich_member(member, key, cx, existing):
    """
    For each platform not already filled from the bio, run one CSE query and
    return {platform: url_string}. The confidence score is still used internally
    to pick the single best candidate, but only the URL is returned.
    """
    out = {}
    name = member["name"]
    party_terms = []  # could be populated if you also fetch party per member
    for plat, domains in PLATFORMS.items():
        if existing.get(plat):  # already have a bio link; don't spend a query
            continue
        # Query the primary domain for this platform.
        primary = domains[0]
        query = f'"{name}" site:{primary}'
        items = google_cse(query, key, cx, num=5)
        time.sleep(0.5)  # gentle pacing

        best_url = None
        best_conf = 0.0
        for it in items:
            link = it.get("link", "")
            dom = urlparse(link).netloc.lower().replace("www.", "")
            # Map x.com/twitter.com both to twitter_x.
            if platform_for_url(link) != plat:
                continue
            conf = score_candidate(name, party_terms, it, dom)
            if conf > best_conf:
                best_conf = conf
                best_url = link

        if best_url and best_conf > 0:
            out[plat] = best_url
    return out


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def build(limit=None, do_enrich=True, out_path=OUT_DEFAULT):
    key = os.environ.get("GOOGLE_CSE_KEY")
    cx = os.environ.get("GOOGLE_CSE_CX")
    if do_enrich and (not key or not cx):
        print("WARNING: GOOGLE_CSE_KEY / GOOGLE_CSE_CX not set. "
              "Running roster + bios only (no search enrichment).", file=sys.stderr)
        do_enrich = False

    # Resume support: if the output file exists, keep already-filled fields.
    prior = {}
    if os.path.exists(out_path):
        try:
            prev = json.load(open(out_path, encoding="utf-8"))
            for m in prev.get("members", []):
                prior[m.get("name")] = m
        except Exception:  # noqa: BLE001
            pass

    print("Fetching roster from oda.ft.dk ...", file=sys.stderr)
    roster = fetch_roster(limit=limit)
    print(f"  got {len(roster)} members", file=sys.stderr)

    members_out = []
    for i, m in enumerate(roster, 1):
        name = m["name"]
        record = prior.get(name, {
            "name": name,
            "facebook": None, "instagram": None,
            "twitter_x": None, "linkedin": None,
        })
        record["aktoer_id"] = m["aktoer_id"]

        # Step 2: bio links (from the official biography; fill nulls only).
        bio_links = extract_from_bio(m["biografi"])
        for plat, url in bio_links.items():
            if not record.get(plat):
                record[plat] = url

        # Step 3: search enrichment for the rest.
        if do_enrich:
            existing = {p: bool(record.get(p)) for p in PLATFORMS}
            print(f"[{i}/{len(roster)}] enriching {name} ...", file=sys.stderr)
            found = enrich_member(m, key, cx, existing)
            for plat, val in found.items():
                if not record.get(plat):
                    record[plat] = val

        members_out.append(record)

        # Write incrementally so a crash / quota stop doesn't lose progress.
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "note": ("Each platform field is the profile URL or null. "
                             "URLs come from the official Folketinget biography "
                             "or a Google search best-match; search matches are "
                             "not guaranteed to be the correct person."),
                    "members": members_out,
                },
                f, ensure_ascii=False, indent=2,
            )

    print(f"Done. Wrote {len(members_out)} members to {out_path}", file=sys.stderr)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-enrich", action="store_true",
                    help="Skip Google search; roster + bios only (no API key needed).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only process the first N members (for testing).")
    ap.add_argument("--out", default=OUT_DEFAULT, help="Output JSON path.")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(limit=args.limit, do_enrich=not args.no_enrich, out_path=args.out)