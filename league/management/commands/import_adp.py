# league/management/commands/import_adp.py

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from io import StringIO
from typing import Optional

import requests
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from league.models import Player


DEFAULT_URL = "https://www.fantasypros.com/nhl/adp/overall.php"
DEFAULT_TIMEOUT = 25

# IMPORTANT: Only strip a trailing token if it's a REAL NHL team abbreviation.
TEAM_ABBRS = {
    "ANA","ARI","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET","EDM","FLA","LAK",
    "MIN","MTL","NJD","NSH","NYI","NYR","OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR",
    "VAN","VGK","WSH","WPG",
    # Utah (FantasyPros currently uses UTA)
    "UTA",
    # Common alternates you may encounter on sites:
    "NJ","TB","LA","SJ",
}



@dataclass(frozen=True)
class AdpRow:
    rank: int
    name: str
    team: str
    pos: str
    yahoo: Optional[float]
    espn: Optional[float]
    cbs: Optional[float]
    avg: Optional[float]


def _to_int(val) -> Optional[int]:
    try:
        if pd.isna(val):
            return None
        return int(str(val).strip())
    except Exception:
        return None


def _to_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        s = str(val).strip()
        if s == "" or s.lower() in {"na", "n/a", "none", "-"}:
            return None
        return float(s)
    except Exception:
        return None


def _clean_name(name: str) -> str:
    return " ".join(str(name).replace("\u00a0", " ").split()).strip()


def _strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch)
    )


def _base_name_key(s: str) -> str:
    """
    Normalize names: case/accents/punct/suffixes.
    Does NOT strip trailing team abbrev. (that's handled separately)
    """
    s = _clean_name(s).lower()
    s = _strip_accents(s)

    # handle "Last, First"
    if "," in s:
        last, first = [p.strip() for p in s.split(",", 1)]
        if last and first:
            s = f"{first} {last}"

    # normalize punctuation
    s = s.replace("st.", "st")
    s = s.replace("'", "")          # O'Reilly -> oreilly
    s = s.replace("-", " ")         # hyphen -> space

    # remove parentheses content
    s = re.sub(r"\([^)]*\)", "", s)

    # remove suffixes
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)

    # keep only letters/spaces
    s = re.sub(r"[^a-z\s]", " ", s)

    return " ".join(s.split())


def _adp_name_key(s: str) -> str:
    """
    Key for FantasyPros "Player" cells, which often look like:
      'Connor McDavid EDM'
    We strip ONLY a real NHL team abbreviation from the end.
    """
    s = _clean_name(s)

    # If the raw string ends with a team token (EDM/COL/VGK/etc), remove it BEFORE normalization
    parts = s.split()
    if parts:
        last = parts[-1].upper()
        if last in TEAM_ABBRS:
            s = " ".join(parts[:-1])

    k = _base_name_key(s)

    # known typo sometimes seen
    k = k.replace("alexandar georgiev", "alexander georgiev")
    return k


def _db_name_key(s: str) -> str:
    """
    Key for your DB Player.full_name.
    DO NOT strip 2-4 letter tokens (that was the bug: Fox/Hill/Aho/etc).
    """
    k = _base_name_key(s)
    k = k.replace("alexandar georgiev", "alexander georgiev")
    return k


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    cols = list(df.columns)
    looks_unnamed = all(
        isinstance(c, int) or str(c).strip().lower().startswith("unnamed")
        for c in cols
    )
    if not looks_unnamed:
        return df

    first_row = [str(x).strip() for x in df.iloc[0].tolist()]
    first_lc = [x.lower() for x in first_row]
    if "rank" in first_lc and "player" in first_lc and ("avg" in first_lc or "pos" in first_lc):
        df2 = df.copy()
        df2.columns = first_row
        df2 = df2.iloc[1:].reset_index(drop=True)
        return df2

    return df


def _pick_adp_table(tables: list[pd.DataFrame]) -> pd.DataFrame:
    wanted = ["rank", "player", "team", "pos", "avg", "yahoo", "espn", "cbs"]

    best: Optional[pd.DataFrame] = None
    best_score = -1

    for t in tables:
        t = _normalize_headers(t)
        cols = [str(c).strip().lower() for c in t.columns]

        score = 0
        for w in wanted:
            if any(c == w or w in c for c in cols):
                score += 1

        if score > best_score:
            best = t
            best_score = score

    if best is None or best_score < 4:
        raise CommandError("Could not locate ADP table in the HTML (headers may be missing/shifted).")

    return best


def _fetch_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _find_col(adp_df: pd.DataFrame, target: str) -> Optional[str]:
    t = target.lower()
    for c in adp_df.columns:
        c_lc = str(c).strip().lower()
        if c_lc == t or t in c_lc:
            return c
    return None


def _parse_from_html(url: str) -> list[AdpRow]:
    html = _fetch_html(url)

    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        raise CommandError("No tables found in HTML. Source may have changed.")

    adp_df = _pick_adp_table(tables)

    rank_col = _find_col(adp_df, "rank")
    player_col = _find_col(adp_df, "player")
    team_col = _find_col(adp_df, "team")
    pos_col = _find_col(adp_df, "pos")
    avg_col = _find_col(adp_df, "avg")

    missing = [
        n for n, c in [
            ("rank", rank_col),
            ("player", player_col),
            ("team", team_col),
            ("pos", pos_col),
            ("avg", avg_col),
        ] if c is None
    ]
    if missing:
        raise CommandError(
            f"ADP table found, but missing expected columns: {missing}. "
            f"Found columns: {[str(c) for c in adp_df.columns]}"
        )

    yahoo_col = _find_col(adp_df, "yahoo")
    espn_col = _find_col(adp_df, "espn")
    cbs_col = _find_col(adp_df, "cbs")

    rows: list[AdpRow] = []
    for _, r in adp_df.iterrows():
        rank = _to_int(r[rank_col])
        name = _clean_name(r[player_col])
        team = _clean_name(r[team_col])
        pos = _clean_name(r[pos_col])
        avg = _to_float(r[avg_col])

        yahoo = _to_float(r[yahoo_col]) if yahoo_col else None
        espn = _to_float(r[espn_col]) if espn_col else None
        cbs = _to_float(r[cbs_col]) if cbs_col else None

        if rank is None or not name:
            continue

        rows.append(
            AdpRow(
                rank=rank,
                name=name,
                team=team,
                pos=pos,
                yahoo=yahoo,
                espn=espn,
                cbs=cbs,
                avg=avg,
            )
        )

    if not rows:
        raise CommandError("No ADP rows parsed. The table may be empty or the layout changed.")

    return rows


class Command(BaseCommand):
    help = "Import player ADP into Player.adp (FantasyPros by default)."

    def add_arguments(self, parser):
        parser.add_argument("--url", type=str, default=DEFAULT_URL)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--debug-missing", type=int, default=0, help="Print first N missing name pairs")

    def handle(self, *args, **options):
        url: str = options["url"]
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"] or 0
        debug_missing: int = options["debug_missing"] or 0

        self.stdout.write(f"Fetching ADP from: {url}")
        adp_rows = _parse_from_html(url)

        if limit > 0:
            adp_rows = adp_rows[:limit]

        # Your model field
        name_field = "full_name"
        players = Player.objects.all().only("id", name_field, "adp", "nhl_id")

        # DB key map (DO NOT strip team suffix here)
        by_name: dict[str, Player] = {}
        for p in players:
            val = getattr(p, name_field, None)
            if not val:
                continue
            by_name[_db_name_key(val)] = p

        wrote = 0
        matched = 0
        missing = 0
        missing_samples: list[tuple[str, str]] = []

        def apply_updates():
            nonlocal wrote, matched, missing
            for row in adp_rows:
                key = _adp_name_key(row.name)
                p = by_name.get(key)
                if not p:
                    missing += 1
                    if debug_missing and len(missing_samples) < debug_missing:
                        missing_samples.append((row.name, key))
                    continue

                matched += 1
                new_adp = row.avg if row.avg is not None else float(row.rank)

                if p.adp is not None and float(p.adp) == float(new_adp):
                    continue

                p.adp = new_adp
                p.save(update_fields=["adp"])
                wrote += 1

        if dry_run:
            for row in adp_rows:
                if _adp_name_key(row.name) in by_name:
                    matched += 1
                else:
                    missing += 1
                    if debug_missing and len(missing_samples) < debug_missing:
                        missing_samples.append((row.name, _adp_name_key(row.name)))
            self.stdout.write(self.style.WARNING("DRY RUN (no DB writes)"))
        else:
            with transaction.atomic():
                apply_updates()

        self.stdout.write("")
        self.stdout.write(f"Parsed rows: {len(adp_rows)}")
        self.stdout.write(f"Matched players: {matched}")
        self.stdout.write(f"Wrote updates: {wrote}")
        self.stdout.write(f"Missing (no name match): {missing}")

        if missing_samples:
            self.stdout.write("")
            self.stdout.write("Sample missing (FantasyPros name -> normalized key):")
            for raw, key in missing_samples:
                self.stdout.write(f"  - {raw}  ->  {key}")

        if len(adp_rows) > 0 and matched == 0:
            raise CommandError(
                "Parsed ADP rows, but matched 0 players. "
                "Run with --dry-run --debug-missing 20 to see what names are not matching."
            )
