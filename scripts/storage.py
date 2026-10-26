"""SQLite persistence for Game Radar. Standard library only.

GitHub Actions checks out the committed database, updates it transactionally,
and commits it back. GitHub Pages continues to consume data/games.json.
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS game_info (
 appid INTEGER PRIMARY KEY, name TEXT NOT NULL, name_en TEXT,
 genres_json TEXT NOT NULL DEFAULT '[]', review_pct REAL, review_count INTEGER,
 recommend_score REAL, release_date TEXT, coming_soon INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steam_price_history (
 appid INTEGER NOT NULL, observed_date TEXT NOT NULL, currency TEXT NOT NULL DEFAULT 'CNY',
 price REAL NOT NULL, original_price REAL, discount_pct INTEGER,
 source TEXT NOT NULL DEFAULT 'steam_store',
 PRIMARY KEY(appid,observed_date,currency,source)
);
CREATE INDEX IF NOT EXISTS idx_steam_price_date ON steam_price_history(observed_date);
CREATE TABLE IF NOT EXISTS key_price_history (
 appid INTEGER NOT NULL, observed_date TEXT NOT NULL, platform TEXT NOT NULL,
 package_id TEXT NOT NULL DEFAULT '', price REAL NOT NULL, kind TEXT NOT NULL,
 status TEXT NOT NULL, source_url TEXT, checked_at TEXT,
 PRIMARY KEY(appid,observed_date,platform,package_id,kind)
);
CREATE INDEX IF NOT EXISTS idx_key_price_date ON key_price_history(observed_date);
CREATE TABLE IF NOT EXISTS epic_free_history (
 game_key TEXT PRIMARY KEY, title TEXT NOT NULL, giveaway_date TEXT, store_url TEXT,
 source_url TEXT, last_checked TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mobile_platform (
 appid INTEGER PRIMARY KEY, android TEXT, ios TEXT,
 status TEXT, source_url TEXT, verified_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steam_deck_info (
 appid INTEGER PRIMARY KEY, compatibility TEXT, source_url TEXT, checked_at TEXT
);
CREATE TABLE IF NOT EXISTS game_dlc (
 appid INTEGER NOT NULL, dlc_appid INTEGER NOT NULL,
 name TEXT, price_cny REAL, recommended INTEGER, source_url TEXT, checked_at TEXT,
 PRIMARY KEY(appid,dlc_appid)
);
CREATE TABLE IF NOT EXISTS user_owned_games (
 name TEXT PRIMARY KEY, appid INTEGER, updated_at TEXT NOT NULL
);
"""

def now_cn():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))

def setup(conn):
    conn.executescript(SCHEMA)
    # Safe additive migration for databases created before release-date support.
    existing = {row[1] for row in conn.execute("PRAGMA table_info(game_info)")}
    if "release_date" not in existing:
        conn.execute("ALTER TABLE game_info ADD COLUMN release_date TEXT")
    if "coming_soon" not in existing:
        conn.execute("ALTER TABLE game_info ADD COLUMN coming_soon INTEGER NOT NULL DEFAULT 0")

def _valid_price(value):
    try:
        if value is None or isinstance(value, bool): return None
        n = float(value)
        return n if 0 < n < 100000 else None
    except (ValueError, TypeError):
        return None

def save(db_path, games, raw, config, hist, epic_records, observed=None):
    """Persist a complete daily candidate price scan and enriched shortlist.

    Price snapshots are unique per local calendar day. Reruns update existing
    daily records; source-specific observations remain distinct.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    moment = observed or now_cn()
    date = moment.date().isoformat()
    stamp = moment.isoformat()
    with sqlite3.connect(db_path) as conn:
        setup(conn)
        with conn:
            # Seed former JSON minima only as a separate baseline; no fabricated date.
            # Real daily observations start with this database migration.
            for game in games:
                aid = game.get("appid")
                if not isinstance(aid, int): continue
                conn.execute("""
                    INSERT INTO game_info(appid,name,name_en,genres_json,review_pct,review_count,recommend_score,release_date,coming_soon,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(appid) DO UPDATE SET
                      name=excluded.name,name_en=excluded.name_en,
                      genres_json=excluded.genres_json,review_pct=excluded.review_pct,
                      review_count=excluded.review_count,
                      recommend_score=excluded.recommend_score,release_date=excluded.release_date,
                      coming_soon=excluded.coming_soon,updated_at=excluded.updated_at
                """,(aid,game.get("name") or str(aid),game.get("name_en"),
                    json.dumps(game.get("genres") or [],ensure_ascii=False),
                    game.get("review_pct"),game.get("review_count"),
                    game.get("recommend_score"),game.get("release_date"),int(bool(game.get("coming_soon"))),stamp))

                mobile = game.get("mobile")
                if isinstance(mobile,dict) and (mobile.get("android") or mobile.get("ios")):
                    conn.execute("""
                        INSERT INTO mobile_platform(appid,android,ios,status,source_url,verified_at)
                        VALUES(?,?,?,?,?,?)
                        ON CONFLICT(appid) DO UPDATE SET
                          android=excluded.android,ios=excluded.ios,status=excluded.status,
                          source_url=excluded.source_url,verified_at=excluded.verified_at
                    """,(aid,mobile.get("android"),mobile.get("ios"),
                        mobile.get("status"),mobile.get("source"),stamp))

                deck = game.get("steam_deck")
                if isinstance(deck,dict) and deck.get("compatibility"):
                    conn.execute("""
                        INSERT INTO steam_deck_info(appid,compatibility,source_url,checked_at)
                        VALUES(?,?,?,?)
                        ON CONFLICT(appid) DO UPDATE SET
                          compatibility=excluded.compatibility,
                          source_url=excluded.source_url,checked_at=excluded.checked_at
                    """,(aid,deck.get("compatibility"),deck.get("source"),stamp))

                for offer in game.get("key_offers") or []:
                    value = _valid_price(offer.get("price"))
                    if value is None or not offer.get("platform"): continue
                    conn.execute("""
                        INSERT INTO key_price_history
                        (appid,observed_date,platform,package_id,price,kind,status,source_url,checked_at)
                        VALUES(?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(appid,observed_date,platform,package_id,kind) DO UPDATE SET
                          price=excluded.price,status=excluded.status,
                          source_url=excluded.source_url,checked_at=excluded.checked_at
                    """,(aid,date,offer["platform"],str(offer.get("subid") or ""),
                         value,offer.get("kind") or "reference",offer.get("status") or "",
                         offer.get("url"),offer.get("checked_at") or stamp))

            # Raw Steam special/new-release candidates, including ones that did
            # not make the 24 displayed cards.
            for item in raw:
                aid=item.get("id")
                if not isinstance(aid,int):continue
                cents=item.get("final_price")
                if not isinstance(cents,(int,float)) or cents<=0:continue
                value=_valid_price(cents/100)
                if value is None:continue
                orig=item.get("original_price")
                original=orig/100 if isinstance(orig,(int,float)) and orig>0 else None
                conn.execute("""
                    INSERT INTO steam_price_history
                    (appid,observed_date,currency,price,original_price,discount_pct,source)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(appid,observed_date,currency,source) DO UPDATE SET
                      price=excluded.price,original_price=excluded.original_price,
                      discount_pct=excluded.discount_pct
                """,(aid,date,"CNY",value,original,item.get("discount_percent"),"steam_store"))

            for key, entry in (epic_records or {}).items():
                if not isinstance(entry,dict) or not entry.get("title"):continue
                conn.execute("""
                    INSERT INTO epic_free_history
                    (game_key,title,giveaway_date,store_url,source_url,last_checked)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(game_key) DO UPDATE SET
                      title=excluded.title,giveaway_date=excluded.giveaway_date,
                      store_url=excluded.store_url,source_url=excluded.source_url,
                      last_checked=excluded.last_checked
                """,(key,entry["title"],entry.get("date"),entry.get("url"),
                    entry.get("source"),stamp))

            # Match configured owned names (preserve manual selection).
            conn.execute("DELETE FROM user_owned_games")
            for name in config.get("owned",[]):
                if name:
                    conn.execute(
                        "INSERT INTO user_owned_games(name,updated_at) VALUES(?,?)",
                        (name,stamp)
                    )
    return {"date":date,"games_enriched":len(games),
            "steam_candidates":len(raw),"epic_archive":len(epic_records or {})}

def statistics(db_path):
    with sqlite3.connect(db_path) as c:
        return {name:c.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in ("game_info","steam_price_history","key_price_history",
                             "epic_free_history","mobile_platform","steam_deck_info",
                             "game_dlc","user_owned_games")}
