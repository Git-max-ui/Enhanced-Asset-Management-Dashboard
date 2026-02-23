import sqlite3
from collections import Counter
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "assets.db"
DEFAULT_USER_KEY = "default_user"

DEFAULT_CATEGORIES = [
    ("手机", "📱"),
    ("平板", "📝"),
    ("电脑", "💻"),
    ("耳机", "🎧"),
    ("衣服", "👕"),
    ("鞋子", "👟"),
    ("包", "👜"),
    ("书", "📚"),
    ("键盘", "⌨️"),
    ("鼠标", "🖱️"),
]

CATEGORY_KEYWORDS = {
    "手机": ["iphone", "手机", "安卓", "galaxy", "xiaomi", "huawei"],
    "平板": ["ipad", "平板", "tablet"],
    "电脑": ["电脑", "macbook", "笔记本", "台式机", "pc"],
    "耳机": ["耳机", "airpods", "headset", "buds"],
    "衣服": ["衣", "外套", "裤", "t恤", "衬衫"],
    "鞋子": ["鞋", "sneaker", "跑鞋"],
    "包": ["包", "backpack", "手提包"],
    "书": ["书", "教材", "读物", "ebook"],
    "键盘": ["键盘", "keyboard"],
    "鼠标": ["鼠标", "mouse"],
}


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _table_columns(conn, table_name: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _categories_has_legacy_unique_name(conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'categories'")
    row = cur.fetchone()
    if not row or not row[0]:
        return False
    table_sql = str(row[0]).lower()
    return "name text not null unique" in table_sql


def _migrate_categories_table(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL DEFAULT 'default_user',
            name TEXT NOT NULL,
            logo TEXT NOT NULL DEFAULT '📦'
        )
        """
    )
    cur.execute(
        """
        INSERT INTO categories_new (id, user_key, name, logo)
        SELECT id,
               COALESCE(NULLIF(user_key, ''), 'default_user'),
               name,
               COALESCE(NULLIF(logo, ''), '📦')
        FROM categories
        """
    )
    cur.execute("DROP TABLE categories")
    cur.execute("ALTER TABLE categories_new RENAME TO categories")
    conn.commit()


def _deduplicate_categories(conn):
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM categories
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM categories
            GROUP BY COALESCE(NULLIF(user_key, ''), 'default_user'), name
        )
        """
    )
    conn.commit()


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL DEFAULT 'default_user',
            name TEXT NOT NULL,
            logo TEXT NOT NULL DEFAULT '📦'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL DEFAULT 'default_user',
            name TEXT NOT NULL,
            category TEXT,
            category_id INTEGER,
            category_name TEXT NOT NULL,
            category_logo TEXT NOT NULL DEFAULT '📦',
            price REAL NOT NULL,
            purchase_date TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL DEFAULT 'default_user',
            name TEXT NOT NULL,
            category_name TEXT NOT NULL,
            category_logo TEXT NOT NULL DEFAULT '💡',
            target_price REAL NOT NULL,
            priority TEXT NOT NULL DEFAULT '中',
            note TEXT DEFAULT '',
            created_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '想买'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            query TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cols = _table_columns(conn, "assets")
    if "user_key" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN user_key TEXT NOT NULL DEFAULT 'default_user'")
    if "category_id" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN category_id INTEGER")
    if "category_name" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN category_name TEXT")
    if "category_logo" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN category_logo TEXT NOT NULL DEFAULT '📦'")
    if "custom_tags" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN custom_tags TEXT NOT NULL DEFAULT ''")
    if "price_tag" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN price_tag TEXT NOT NULL DEFAULT ''")
    if "frequency_tag" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN frequency_tag TEXT NOT NULL DEFAULT '日常'")
    if "maintenance_date" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN maintenance_date TEXT")
    if "asset_status" not in cols:
        cur.execute("ALTER TABLE assets ADD COLUMN asset_status TEXT NOT NULL DEFAULT '使用中'")

    cat_cols = _table_columns(conn, "categories")
    if "user_key" not in cat_cols:
        cur.execute("ALTER TABLE categories ADD COLUMN user_key TEXT NOT NULL DEFAULT 'default_user'")

    if _categories_has_legacy_unique_name(conn):
        _migrate_categories_table(conn)

    wish_cols = _table_columns(conn, "wishlist")
    if "user_key" not in wish_cols:
        cur.execute("ALTER TABLE wishlist ADD COLUMN user_key TEXT NOT NULL DEFAULT 'default_user'")
    if "converted_asset_id" not in wish_cols:
        cur.execute("ALTER TABLE wishlist ADD COLUMN converted_asset_id INTEGER")

    conn.commit()

    cur.execute(
        """
        UPDATE categories
        SET user_key = COALESCE(NULLIF(user_key, ''), ?)
        """,
        (DEFAULT_USER_KEY,),
    )

    cur.execute(
        """
        UPDATE wishlist
        SET user_key = COALESCE(NULLIF(user_key, ''), ?)
        """,
        (DEFAULT_USER_KEY,),
    )

    cur.execute(
        """
        UPDATE assets
        SET user_key = COALESCE(NULLIF(user_key, ''), ?)
        """,
        (DEFAULT_USER_KEY,),
    )

    for name, logo in DEFAULT_CATEGORIES:
        cur.execute(
            """
            INSERT INTO categories (user_key, name, logo)
            SELECT ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM categories WHERE user_key = ? AND name = ?
            )
            """,
            (DEFAULT_USER_KEY, name, logo, DEFAULT_USER_KEY, name),
        )

    # 兼容旧版本数据：把 assets.category 回填到 category_name
    cols_after = _table_columns(conn, "assets")
    if "category" in cols_after:
        cur.execute(
            """
            UPDATE assets
            SET category_name = COALESCE(NULLIF(category_name, ''), category, '未分类')
            """
        )
        cur.execute(
            """
            UPDATE assets
            SET category = COALESCE(NULLIF(category, ''), category_name, '未分类')
            """
        )
    else:
        cur.execute(
            """
            UPDATE assets
            SET category_name = COALESCE(NULLIF(category_name, ''), '未分类')
            """
        )

    cur.execute(
        """
        UPDATE assets
        SET category_logo = COALESCE(NULLIF(category_logo, ''), '📦')
        """
    )

    cur.execute(
        """
        UPDATE assets
        SET custom_tags = COALESCE(custom_tags, '')
        """
    )

    cur.execute(
        """
        UPDATE assets
        SET frequency_tag = COALESCE(NULLIF(frequency_tag, ''), '日常')
        """
    )

    cur.execute(
        """
        UPDATE assets
        SET asset_status = COALESCE(NULLIF(asset_status, ''), '使用中')
        """
    )

    cur.execute(
        """
        UPDATE assets
        SET price_tag = CASE
            WHEN price < 500 THEN '低'
            WHEN price <= 5000 THEN '中'
            ELSE '高'
        END
        WHERE COALESCE(NULLIF(price_tag, ''), '') = ''
        """
    )

    # 尝试用 categories 修正 logo
    cur.execute(
        """
        UPDATE assets
        SET category_logo = (
            SELECT c.logo FROM categories c WHERE c.id = assets.category_id AND c.user_key = assets.user_key
        )
        WHERE category_id IS NOT NULL
        """
    )

    conn.commit()

    # 去重后再创建唯一索引，避免历史重复数据导致崩溃
    _deduplicate_categories(conn)

    # 按 user_key 拆分 categories 的唯一约束能力（旧表结构是 name 全局唯一）
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_name ON categories(user_key, name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_assets_user_key ON assets(user_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wishlist_user_key ON wishlist(user_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_search_user_key ON search_history(user_key)")
    conn.commit()
    conn.close()


def normalize_user_key(user_input: str) -> str:
    key = (user_input or "").strip().lower().replace(" ", "_")
    return key if key else DEFAULT_USER_KEY


def normalize_tags(tags: list[str] | str | None) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw = tags.replace("，", ",")
        items = [t.strip() for t in raw.split(",") if t.strip()]
    else:
        items = [str(t).strip() for t in tags if str(t).strip()]
    cleaned = []
    for item in items:
        cleaned.append(item if item.startswith("#") else f"#{item}")
    # 保序去重
    unique = []
    seen = set()
    for tag in cleaned:
        if tag not in seen:
            unique.append(tag)
            seen.add(tag)
    return unique


def tags_to_text(tags: list[str] | str | None) -> str:
    return ",".join(normalize_tags(tags))


def tags_from_text(tags_text: str | None) -> list[str]:
    return normalize_tags(tags_text or "")


def infer_price_tag(price: float) -> str:
    if price < 500:
        return "低"
    if price <= 5000:
        return "中"
    return "高"


def recommend_category(name: str, categories: list[dict]) -> dict | None:
    text = (name or "").strip().lower()
    if not text:
        return None
    for category_name, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            for c in categories:
                if c["name"] == category_name:
                    return c
    return None


def ensure_default_categories_for_user(user_key: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) FROM categories WHERE user_key = ?", (user_key,))
    existing = int(cur.fetchone()[0])
    if existing >= len(DEFAULT_CATEGORIES):
        conn.close()
        return

    for name, logo in DEFAULT_CATEGORIES:
        cur.execute(
            """
            INSERT INTO categories (user_key, name, logo)
            SELECT ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM categories WHERE user_key = ? AND name = ?
            )
            """,
            (user_key, name, logo, user_key, name),
        )
    conn.commit()
    conn.close()


def fetch_categories(user_key: str):
    user_key = normalize_user_key(user_key)
    ensure_default_categories_for_user(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, logo FROM categories WHERE user_key = ? ORDER BY id ASC",
        (user_key,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_category(user_key: str, name: str, logo: str):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO categories (user_key, name, logo) VALUES (?, ?, ?)",
        (user_key, name.strip(), (logo or "📦").strip()),
    )
    conn.commit()
    conn.close()


def delete_category(user_key: str, category_id: int):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE assets SET category_id = NULL WHERE category_id = ? AND user_key = ?",
        (category_id, user_key),
    )
    cur.execute("DELETE FROM categories WHERE id = ? AND user_key = ?", (category_id, user_key))
    conn.commit()
    conn.close()


def _resolve_category(user_key: str, category_id: int | None, custom_name: str, custom_logo: str):
    user_key = normalize_user_key(user_key)
    if custom_name.strip():
        return None, custom_name.strip(), (custom_logo or "📦").strip()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, logo FROM categories WHERE id = ? AND user_key = ?",
        (category_id, user_key),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None, "未分类", "📦"
    return row["id"], row["name"], row["logo"]


def add_asset(
    user_key: str,
    name: str,
    category_id: int | None,
    custom_category_name: str,
    custom_logo: str,
    price: float,
    purchase_date: date,
    frequency_tag: str = "日常",
    custom_tags: list[str] | str | None = None,
    maintenance_date: date | None = None,
    asset_status: str = "使用中",
):
    user_key = normalize_user_key(user_key)
    cid, cname, clogo = _resolve_category(user_key, category_id, custom_category_name, custom_logo)
    price_tag = infer_price_tag(float(price))
    tags_text = tags_to_text(custom_tags)
    maintenance_date_text = maintenance_date.isoformat() if isinstance(maintenance_date, date) else None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO assets (
            user_key, name, category, category_id, category_name, category_logo,
            price, purchase_date, frequency_tag, custom_tags, price_tag, maintenance_date, asset_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_key,
            name.strip(),
            cname,
            cid,
            cname,
            clogo,
            float(price),
            purchase_date.isoformat(),
            frequency_tag or "日常",
            tags_text,
            price_tag,
            maintenance_date_text,
            asset_status or "使用中",
        ),
    )
    conn.commit()
    conn.close()


def update_asset(
    user_key: str,
    asset_id: int,
    name: str,
    category_id: int | None,
    custom_category_name: str,
    custom_logo: str,
    price: float,
    purchase_date: date,
    frequency_tag: str = "日常",
    custom_tags: list[str] | str | None = None,
    maintenance_date: date | None = None,
    asset_status: str = "使用中",
):
    user_key = normalize_user_key(user_key)
    cid, cname, clogo = _resolve_category(user_key, category_id, custom_category_name, custom_logo)
    price_tag = infer_price_tag(float(price))
    tags_text = tags_to_text(custom_tags)
    maintenance_date_text = maintenance_date.isoformat() if isinstance(maintenance_date, date) else None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE assets
        SET name = ?, category = ?, category_id = ?, category_name = ?, category_logo = ?,
            price = ?, purchase_date = ?, frequency_tag = ?, custom_tags = ?, price_tag = ?, maintenance_date = ?, asset_status = ?
        WHERE id = ? AND user_key = ?
        """,
        (
            name.strip(),
            cname,
            cid,
            cname,
            clogo,
            float(price),
            purchase_date.isoformat(),
            frequency_tag or "日常",
            tags_text,
            price_tag,
            maintenance_date_text,
            asset_status or "使用中",
            asset_id,
            user_key,
        ),
    )
    conn.commit()
    conn.close()


def delete_asset(user_key: str, asset_id: int):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM assets WHERE id = ? AND user_key = ?", (asset_id, user_key))
    conn.commit()
    conn.close()


def fetch_assets(
    user_key: str,
    search_text: str = "",
    category_name: str = "全部",
    tag_filter: str = "全部",
    price_tag_filter: str = "全部",
    start_date: date | None = None,
    end_date: date | None = None,
):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()

    where = ["user_key = ?"]
    params = [user_key]

    if search_text.strip():
        where.append("(name LIKE ? OR category_name LIKE ? OR custom_tags LIKE ?)")
        kw = f"%{search_text.strip()}%"
        params.extend([kw, kw, kw])

    if category_name != "全部":
        where.append("category_name = ?")
        params.append(category_name)

    if tag_filter != "全部":
        where.append("custom_tags LIKE ?")
        params.append(f"%{tag_filter}%")

    if price_tag_filter != "全部":
        where.append("price_tag = ?")
        params.append(price_tag_filter)

    if start_date is not None:
        where.append("purchase_date >= ?")
        params.append(start_date.isoformat())

    if end_date is not None:
        where.append("purchase_date <= ?")
        params.append(end_date.isoformat())

    sql = "SELECT * FROM assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_all_assets():
    return fetch_assets(DEFAULT_USER_KEY)


def fetch_all_assets_by_user(user_key: str):
    return fetch_assets(user_key)


def calc_usage_days(purchase_date_text: str) -> int:
    purchased = datetime.strptime(purchase_date_text, "%Y-%m-%d").date()
    days = (date.today() - purchased).days + 1
    return max(days, 1)


def format_duration(days: int) -> str:
    years = days // 365
    remain = days % 365
    months = remain // 30
    d = remain % 30
    parts = []
    if years:
        parts.append(f"{years}年")
    if months:
        parts.append(f"{months}月")
    if d or not parts:
        parts.append(f"{d}天")
    return "".join(parts)


def build_display_rows(rows):
    display = []
    total_price = 0.0
    total_daily_price = 0.0

    for r in rows:
        usage_days = calc_usage_days(r["purchase_date"])
        daily_price = float(r["price"]) / usage_days
        total_price += float(r["price"])
        total_daily_price += daily_price

        display.append(
            {
                "名称": r["name"],
                "种类": f"{r.get('category_logo', '📦')} {r.get('category_name', '未分类')}",
                "价格(元)": round(float(r["price"]), 2),
                "购入日期": r["purchase_date"],
                "价格标签": r.get("price_tag", infer_price_tag(float(r["price"]))),
                "使用频率": r.get("frequency_tag", "日常"),
                "标签": r.get("custom_tags", ""),
                "状态": r.get("asset_status", "使用中"),
                "保养/到期日": r.get("maintenance_date") or "-",
                "使用天数": usage_days,
                "日均价格(元/天)": round(daily_price, 2),
                "在役时长": format_duration(usage_days),
            }
        )

    return display, total_price, total_daily_price


def add_wish(user_key: str, name: str, category_name: str, category_logo: str, target_price: float, priority: str, note: str):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO wishlist (user_key, name, category_name, category_logo, target_price, priority, note, created_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '想买')
        """,
        (
            user_key,
            name.strip(),
            category_name.strip() if category_name.strip() else "未分类",
            (category_logo or "💡").strip(),
            float(target_price),
            priority,
            note.strip(),
            date.today().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def fetch_wishes(user_key: str, search_text: str = "", status: str = "全部"):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()

    where = ["user_key = ?"]
    params = [user_key]

    if search_text.strip():
        where.append("(name LIKE ? OR category_name LIKE ? OR note LIKE ?)")
        kw = f"%{search_text.strip()}%"
        params.extend([kw, kw, kw])

    if status != "全部":
        where.append("status = ?")
        params.append(status)

    sql = "SELECT * FROM wishlist"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_wish_status(user_key: str, wish_id: int, status: str):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM wishlist WHERE id = ? AND user_key = ?",
        (wish_id, user_key),
    )
    wish = cur.fetchone()
    if wish is None:
        conn.close()
        return

    cur.execute(
        "UPDATE wishlist SET status = ? WHERE id = ? AND user_key = ?",
        (status, wish_id, user_key),
    )

    converted_asset_id = wish["converted_asset_id"] if "converted_asset_id" in wish.keys() else None
    if status == "已购入" and converted_asset_id is None:
        category_name = wish["category_name"] if wish["category_name"] else "未分类"
        category_logo = wish["category_logo"] if wish["category_logo"] else "💡"
        target_price = float(wish["target_price"]) if wish["target_price"] is not None else 0.0
        price_tag = infer_price_tag(target_price)
        purchase_date = date.today().isoformat()

        cur.execute(
            """
            INSERT INTO assets (
                user_key, name, category, category_id, category_name, category_logo,
                price, purchase_date, frequency_tag, custom_tags, price_tag, maintenance_date, asset_status
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, '偶尔', '#心愿单转化', ?, NULL, '使用中')
            """,
            (
                user_key,
                wish["name"],
                category_name,
                category_name,
                category_logo,
                target_price,
                purchase_date,
                price_tag,
            ),
        )
        new_asset_id = cur.lastrowid
        cur.execute(
            "UPDATE wishlist SET converted_asset_id = ? WHERE id = ? AND user_key = ?",
            (new_asset_id, wish_id, user_key),
        )

    conn.commit()
    conn.close()


def delete_wish(user_key: str, wish_id: int):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM wishlist WHERE id = ? AND user_key = ?", (wish_id, user_key))
    conn.commit()
    conn.close()


def fetch_recent_assets(user_key: str, limit: int = 5):
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM assets WHERE user_key = ? ORDER BY id DESC LIMIT ?",
        (user_key, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def fetch_warning_assets(user_key: str, days: int = 30):
    user_key = normalize_user_key(user_key)
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM assets
        WHERE user_key = ?
          AND COALESCE(asset_status, '使用中') != '已处置'
          AND maintenance_date IS NOT NULL
          AND maintenance_date != ''
          AND maintenance_date >= ?
          AND maintenance_date <= date(?, '+' || ? || ' day')
        ORDER BY maintenance_date ASC
        """,
        (user_key, today, today, days),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_tags(rows: list[dict]) -> list[str]:
    all_tags: list[str] = []
    for row in rows:
        all_tags.extend(tags_from_text(row.get("custom_tags", "")))
    return sorted(set(all_tags))


def build_tag_cloud_data(rows: list[dict]) -> list[dict]:
    counter: Counter = Counter()
    for row in rows:
        for tag in tags_from_text(row.get("custom_tags", "")):
            counter[tag] += 1
    return [{"标签": tag, "数量": count} for tag, count in counter.most_common()]


def add_search_history(user_key: str, query: str):
    user_key = normalize_user_key(user_key)
    text = (query or "").strip()
    if not text:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM search_history WHERE user_key = ? AND query = ?", (user_key, text))
    cur.execute(
        "INSERT INTO search_history (user_key, query, created_at) VALUES (?, ?, ?)",
        (user_key, text, datetime.now().isoformat(timespec="seconds")),
    )
    cur.execute(
        """
        DELETE FROM search_history
        WHERE id IN (
            SELECT id FROM search_history
            WHERE user_key = ?
            ORDER BY created_at DESC
            LIMIT -1 OFFSET 10
        )
        """,
        (user_key,),
    )
    conn.commit()
    conn.close()


def fetch_search_history(user_key: str, limit: int = 10) -> list[str]:
    user_key = normalize_user_key(user_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT query FROM search_history WHERE user_key = ? ORDER BY created_at DESC LIMIT ?",
        (user_key, limit),
    )
    rows = [r["query"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_search_suggestions(user_key: str, prefix: str, limit: int = 10) -> list[str]:
    user_key = normalize_user_key(user_key)
    text = (prefix or "").strip()
    if not text:
        return []
    kw = f"%{text}%"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT name AS val FROM assets WHERE user_key = ? AND name LIKE ?
        UNION
        SELECT DISTINCT category_name AS val FROM assets WHERE user_key = ? AND category_name LIKE ?
        UNION
        SELECT DISTINCT query AS val FROM search_history WHERE user_key = ? AND query LIKE ?
        LIMIT ?
        """,
        (user_key, kw, user_key, kw, user_key, kw, limit),
    )
    rows = [r["val"] for r in cur.fetchall()]
    conn.close()
    return rows


def calculate_retention_rate(price: float, usage_days: int) -> float:
    annual_decay = 0.15
    years = usage_days / 365
    rate = 100 * ((1 - annual_decay) ** years)
    return round(max(20.0, min(100.0, rate)), 2)


def calculate_health_scores(rows: list[dict]) -> dict:
    if not rows:
        return {
            "保值率": 0,
            "使用频率": 0,
            "维护状态": 0,
            "必要性": 0,
            "流动性": 0,
            "整体健康度": 0,
        }

    retention_scores = []
    frequency_scores = []
    maintenance_scores = []
    necessity_scores = []
    liquidity_scores = []

    for row in rows:
        usage_days = calc_usage_days(row["purchase_date"])
        retention_scores.append(calculate_retention_rate(float(row["price"]), usage_days))

        freq_map = {"日常": 90, "偶尔": 65, "稀有": 40}
        frequency_scores.append(freq_map.get(row.get("frequency_tag", "日常"), 60))

        md = row.get("maintenance_date")
        if not md:
            maintenance_scores.append(75)
        else:
            days_left = (datetime.strptime(md, "%Y-%m-%d").date() - date.today()).days
            if days_left < 0:
                maintenance_scores.append(30)
            elif days_left <= 30:
                maintenance_scores.append(60)
            else:
                maintenance_scores.append(90)

        tags = set(tags_from_text(row.get("custom_tags", "")))
        if "#工作必需" in tags:
            necessity_scores.append(90)
        elif "#投资品" in tags:
            necessity_scores.append(80)
        elif "#奢侈品" in tags:
            necessity_scores.append(45)
        else:
            necessity_scores.append(65)

        cname = row.get("category_name", "")
        if cname in {"手机", "平板", "电脑"}:
            liquidity_scores.append(80)
        elif cname in {"耳机", "键盘", "鼠标"}:
            liquidity_scores.append(70)
        else:
            liquidity_scores.append(60)

    result = {
        "保值率": round(sum(retention_scores) / len(retention_scores), 2),
        "使用频率": round(sum(frequency_scores) / len(frequency_scores), 2),
        "维护状态": round(sum(maintenance_scores) / len(maintenance_scores), 2),
        "必要性": round(sum(necessity_scores) / len(necessity_scores), 2),
        "流动性": round(sum(liquidity_scores) / len(liquidity_scores), 2),
    }
    result["整体健康度"] = round(
        (result["保值率"] + result["使用频率"] + result["维护状态"] + result["必要性"] + result["流动性"]) / 5,
        2,
    )
    return result
