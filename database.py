import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()

# ================================================================
# SECTION 1 — CONNECTION POOL
# ================================================================

connection_pool = None

def init_db():
    global connection_pool
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    create_schema()
    print("✅ PostgreSQL connected and schema ready")


def get_conn():
    return connection_pool.getconn()

def release_conn(conn):
    connection_pool.putconn(conn)

def execute_query(query, params=None, fetch=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            else:
                result = cur.rowcount
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_conn(conn)


# ================================================================
# SECTION 2 — SCHEMA (All Tables)
# ================================================================

def create_schema():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id              SERIAL PRIMARY KEY,
                    email           VARCHAR(255) UNIQUE NOT NULL,
                    password_hash   TEXT NOT NULL,
                    timezone        VARCHAR(100) DEFAULT 'UTC',
                    role            VARCHAR(20) DEFAULT 'user',
                    admin_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    invite_code     VARCHAR(50),
                    last_login_at   TIMESTAMP,
                    created_at      TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'user';")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_code VARCHAR(50);")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS org_name VARCHAR(150);")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS address VARCHAR(255);")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_invite_code ON users(invite_code) WHERE invite_code IS NOT NULL;")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS social_accounts (
                    id                  SERIAL PRIMARY KEY,
                    user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    platform            VARCHAR(50) NOT NULL,
                    access_token        TEXT NOT NULL,
                    refresh_token       TEXT,
                    token_expires_at    TIMESTAMP,
                    page_id             VARCHAR(255),
                    created_at          TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, platform)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS post_templates (
                    id                  SERIAL PRIMARY KEY,
                    user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    content_text        TEXT NOT NULL,
                    media_url           TEXT,
                    platforms           TEXT[] NOT NULL,
                    recurrence_type     VARCHAR(50) DEFAULT 'ONE_TIME',
                    interval_days       INTEGER DEFAULT 1,
                    start_date          TIMESTAMP NOT NULL,
                    end_date            TIMESTAMP,
                    max_occurrences     INTEGER,
                    occurrence_count    INTEGER DEFAULT 0,
                    timezone            VARCHAR(100) DEFAULT 'UTC',
                    status              VARCHAR(50) DEFAULT 'active',
                    created_at          TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id                      SERIAL PRIMARY KEY,
                    template_id             INTEGER REFERENCES post_templates(id) ON DELETE CASCADE,
                    scheduled_at            TIMESTAMP NOT NULL,
                    confirmation_sent_at    TIMESTAMP,
                    confirmation_token      TEXT,
                    superadmin_token        TEXT,
                    token_used              BOOLEAN DEFAULT FALSE,
                    superadmin_token_used   BOOLEAN DEFAULT FALSE,
                    status                  VARCHAR(50) DEFAULT 'scheduled',
                    approved_at             TIMESTAMP,
                    rejection_reason        TEXT,
                    ai_generated            BOOLEAN DEFAULT FALSE,
                    trigger_type            VARCHAR(50),
                    trigger_name            VARCHAR(200),
                    reposted_from_id        INTEGER REFERENCES scheduled_posts(id) ON DELETE SET NULL,
                    created_at              TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS ai_generated BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS trigger_type VARCHAR(50);")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS trigger_name VARCHAR(200);")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS superadmin_token TEXT;")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS superadmin_token_used BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS reposted_from_id INTEGER REFERENCES scheduled_posts(id) ON DELETE SET NULL;")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS admin_token TEXT;")
            cur.execute("ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS admin_token_used BOOLEAN DEFAULT FALSE;")


            cur.execute("""
                CREATE TABLE IF NOT EXISTS post_targets (
                    id                  SERIAL PRIMARY KEY,
                    scheduled_post_id   INTEGER REFERENCES scheduled_posts(id) ON DELETE CASCADE,
                    platform            VARCHAR(50) NOT NULL,
                    status              VARCHAR(50) DEFAULT 'pending',
                    error_message       TEXT,
                    posted_at           TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id              SERIAL PRIMARY KEY,
                    user_id         INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    persona         VARCHAR(50),
                    industry        VARCHAR(100),
                    brand_name      VARCHAR(100),
                    tone            VARCHAR(50),
                    audience        VARCHAR(100),
                    country_code    VARCHAR(5),
                    language        VARCHAR(20),
                    posts_per_week  INTEGER DEFAULT 3,
                    created_at      TIMESTAMP DEFAULT NOW(),
                    updated_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events_cache (
                    id           SERIAL PRIMARY KEY,
                    country_code VARCHAR(5),
                    event_name   VARCHAR(200),
                    event_date   DATE,
                    event_type   VARCHAR(50),
                    raw_data     JSONB,
                    fetched_at   TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trends_cache (
                    id           SERIAL PRIMARY KEY,
                    country_code VARCHAR(10),
                    platform     VARCHAR(50),
                    topic        VARCHAR(200),
                    score        FLOAT,
                    raw_data     JSONB,
                    fetched_at   TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("ALTER TABLE trends_cache ALTER COLUMN country_code TYPE VARCHAR(10);")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rag_chat_history (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    role       VARCHAR(10) NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_rag_chat_history_user_created
                ON rag_chat_history(user_id, created_at DESC);
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS post_approval_stages (
                    id                              SERIAL PRIMARY KEY,
                    scheduled_post_id               INTEGER UNIQUE REFERENCES scheduled_posts(id) ON DELETE CASCADE,
                    hr_status                       VARCHAR(20) DEFAULT 'pending',
                    hr_approved_at                  TIMESTAMP,
                    hr_rejection_reason             TEXT,
                    superadmin_status               VARCHAR(20) DEFAULT 'pending',
                    superadmin_approved_at          TIMESTAMP,
                    superadmin_rejection_reason     TEXT,
                    created_at                      TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
            ALTER TABLE post_approval_stages
            ADD COLUMN IF NOT EXISTS admin_status VARCHAR(20) DEFAULT 'pending';
            """)

            cur.execute("""
            ALTER TABLE post_approval_stages
            ADD COLUMN IF NOT EXISTS admin_approved_at TIMESTAMP;
            """)

            cur.execute("""
            ALTER TABLE post_approval_stages
            ADD COLUMN IF NOT EXISTS admin_rejection_reason TEXT;
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_approval_stages_post
            ON post_approval_stages(scheduled_post_id);
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_approval_stages_admin_status
            ON post_approval_stages(admin_status);
            """)
            
        conn.commit()
        print("✅ All tables created")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_conn(conn)


# ================================================================
# SECTION 3 — USER QUERIES
# ================================================================

def create_user(email: str, password_hash: str, role: str = "user", admin_id: int = None, invite_code: str = None, org_name: str = None, address: str = None):
    return execute_query(
        "INSERT INTO users (email, password_hash, role, admin_id, invite_code, org_name, address) VALUES (LOWER(TRIM(%s)), %s, %s, %s, %s, %s, %s) RETURNING id, email, role, admin_id, invite_code, org_name, address",
        (email, password_hash, role, admin_id, invite_code, org_name, address),
        fetch="one"
    )

def get_user_by_email(email: str):
    return execute_query(
        "SELECT * FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(%s))",
        (email,),
        fetch="one"
    )

def get_user_by_id(user_id: int):
    return execute_query(
        "SELECT id, email, timezone, role, admin_id, invite_code, last_login_at, created_at FROM users WHERE id = %s",
        (user_id,),
        fetch="one"
    )

def update_last_login(user_id: int):
    return execute_query(
        "UPDATE users SET last_login_at = NOW() WHERE id = %s",
        (user_id,)
    )

def get_all_users():
    return execute_query("""
        SELECT
            u.id, u.email, u.role, u.admin_id, u.last_login_at, u.created_at,
            up.persona, up.industry, up.brand_name,
            ARRAY(
                SELECT platform FROM social_accounts sa WHERE sa.user_id = u.id
            ) AS connected_platforms,
            (SELECT COUNT(*) FROM post_templates pt WHERE pt.user_id = u.id) AS total_templates,
            (SELECT COUNT(*) FROM scheduled_posts sp
             JOIN post_templates pt ON sp.template_id = pt.id
             WHERE pt.user_id = u.id) AS total_posts
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.role != 'superadmin'
        ORDER BY u.created_at DESC
    """, fetch="all")


def get_users_for_admin(admin_id: int):
    return execute_query("""
        SELECT
            u.id, u.email, u.role, u.admin_id, u.last_login_at, u.created_at,
            up.persona, up.industry, up.brand_name,
            ARRAY(
                SELECT platform FROM social_accounts sa WHERE sa.user_id = u.id
            ) AS connected_platforms,
            (SELECT COUNT(*) FROM post_templates pt WHERE pt.user_id = u.id) AS total_templates,
            (SELECT COUNT(*) FROM scheduled_posts sp
             JOIN post_templates pt ON sp.template_id = pt.id
             WHERE pt.user_id = u.id) AS total_posts
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.admin_id = %s AND u.role != 'superadmin'
        ORDER BY u.created_at DESC
    """, (admin_id,), fetch="all")


def get_admins():
    return execute_query(
        "SELECT id, email, role, admin_id, invite_code FROM users WHERE role = 'admin' ORDER BY created_at DESC",
        fetch="all"
    )


def get_admins_overview():
    """One row per organization (admin), with counts for the SuperAdmin org list + social summary panel."""
    return execute_query("""
        SELECT
            a.id, a.email, COALESCE(a.org_name, a.email) AS org_name, a.address, a.created_at,
            (SELECT COUNT(*) FROM users u WHERE u.admin_id = a.id) AS user_count,
            (SELECT COUNT(*) FROM scheduled_posts sp
             JOIN post_templates pt ON sp.template_id = pt.id
             JOIN users u ON pt.user_id = u.id
             WHERE u.admin_id = a.id) AS total_posts,
            (SELECT COALESCE(json_object_agg(sa.platform, sa.cnt), '{}'::json) FROM (
                SELECT sac.platform, COUNT(*) AS cnt
                FROM social_accounts sac
                JOIN users u ON sac.user_id = u.id
                WHERE u.admin_id = a.id
                GROUP BY sac.platform
            ) sa) AS social_accounts
        FROM users a
        WHERE a.role = 'admin'
        ORDER BY a.created_at DESC
    """, fetch="all")


def get_admin_overview_detail(admin_id: int):
    """Single organization's header info, stat boxes, and recent activity for the drill-down page."""
    admin = execute_query(
        "SELECT id, email, COALESCE(org_name, email) AS org_name, address, created_at FROM users WHERE id = %s AND role = 'admin'",
        (admin_id,), fetch="one"
    )
    if not admin:
        return None

    user_count = execute_query(
        "SELECT COUNT(*) AS count FROM users WHERE admin_id = %s", (admin_id,), fetch="one"
    )["count"]

    total_posts = execute_query("""
        SELECT COUNT(*) AS count FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE u.admin_id = %s
    """, (admin_id,), fetch="one")["count"]

    social_accounts = execute_query("""
        SELECT sac.platform, COUNT(*) AS count
        FROM social_accounts sac
        JOIN users u ON sac.user_id = u.id
        WHERE u.admin_id = %s
        GROUP BY sac.platform
    """, (admin_id,), fetch="all")

    recent_activity = execute_query("""
        SELECT sp.id AS post_id, sp.status, sp.created_at, sp.approved_at,
               pt.content_text, u.email AS user_email
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE u.admin_id = %s
        ORDER BY COALESCE(sp.approved_at, sp.created_at) DESC
        LIMIT 15
    """, (admin_id,), fetch="all")

    return {
        "admin": admin,
        "user_count": user_count,
        "total_posts": total_posts,
        "social_accounts": social_accounts,
        "recent_activity": recent_activity
    }


# ================================================================
# SECTION 4 — SOCIAL ACCOUNT QUERIES
# ================================================================

def save_social_account(user_id, platform, access_token, refresh_token=None, token_expires_at=None, page_id=None):
    return execute_query("""
        INSERT INTO social_accounts
            (user_id, platform, access_token, refresh_token, token_expires_at, page_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, platform)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_expires_at = EXCLUDED.token_expires_at,
            page_id = EXCLUDED.page_id
        RETURNING id
    """, (user_id, platform, access_token, refresh_token, token_expires_at, page_id), fetch="one")

def get_social_account(user_id, platform):
    return execute_query(
        "SELECT * FROM social_accounts WHERE user_id = %s AND platform = %s",
        (user_id, platform),
        fetch="one"
    )

def update_access_token(account_id, new_token, new_expiry):
    return execute_query(
        "UPDATE social_accounts SET access_token = %s, token_expires_at = %s WHERE id = %s",
        (new_token, new_expiry, account_id)
    )


# ================================================================
# SECTION 5 — POST TEMPLATE QUERIES
# ================================================================

def create_post_template(user_id, content_text, media_url, platforms, recurrence_type,
                          interval_days, start_date, end_date=None, max_occurrences=None, timezone="UTC"):
    return execute_query("""
        INSERT INTO post_templates
            (user_id, content_text, media_url, platforms, recurrence_type,
             interval_days, start_date, end_date, max_occurrences, timezone)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, content_text, media_url, platforms, recurrence_type,
          interval_days, start_date, end_date, max_occurrences, timezone), fetch="one")

def get_template_by_id(template_id):
    return execute_query(
        "SELECT * FROM post_templates WHERE id = %s",
        (template_id,), fetch="one"
    )

def get_active_templates(user_id):
    return execute_query(
        "SELECT * FROM post_templates WHERE user_id = %s AND status = 'active'",
        (user_id,), fetch="all"
    )

def pause_template(template_id):
    return execute_query(
        "UPDATE post_templates SET status = 'paused' WHERE id = %s",
        (template_id,)
    )

def resume_template(template_id):
    return execute_query(
        "UPDATE post_templates SET status = 'active' WHERE id = %s",
        (template_id,)
    )

def increment_occurrence_count(template_id):
    return execute_query(
        "UPDATE post_templates SET occurrence_count = occurrence_count + 1 WHERE id = %s",
        (template_id,)
    )


# ================================================================
# SECTION 6 — SCHEDULED POST QUERIES
# ================================================================


def get_posts_ready_to_publish():
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE pt.status = 'active'
        AND sp.scheduled_at <= NOW()
        AND (
            sp.status = 'approved'
            OR (sp.status = 'scheduled' AND u.admin_id IS NULL)
        )
    """, fetch="all")


def create_scheduled_post(template_id, scheduled_at, reposted_from_id=None):
    return execute_query(
        """INSERT INTO scheduled_posts (template_id, scheduled_at, reposted_from_id)
           VALUES (%s, %s, %s) RETURNING id""",
        (template_id, scheduled_at, reposted_from_id), fetch="one"
    )

def get_post_by_id(post_id):
    return execute_query("""
        SELECT sp.*, pt.content_text, pt.media_url, pt.platforms, pt.user_id,
               sp.ai_generated, sp.trigger_type, sp.trigger_name, sp.reposted_from_id
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.id = %s
    """, (post_id,), fetch="one")

def get_posts_due_for_confirmation():
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE sp.status = 'scheduled'
        AND pt.status = 'active'
        AND u.admin_id IS NOT NULL
        AND sp.scheduled_at - INTERVAL '30 minutes' <= NOW()
        AND sp.scheduled_at > NOW()
    """, fetch="all")

def get_expired_awaiting_posts():
    return execute_query("""
        SELECT * FROM scheduled_posts
        WHERE status IN ('awaiting_hr_approval', 'awaiting_admin_approval')
        AND scheduled_at <= NOW()
    """, fetch="all")

def update_post_status(post_id, status):
    return execute_query(
        "UPDATE scheduled_posts SET status = %s WHERE id = %s",
        (status, post_id)
    )

def get_posts_for_calendar(user_id, start_date, end_date):
    return execute_query("""
        SELECT sp.id, sp.scheduled_at, sp.status, pt.content_text, pt.platforms, pt.media_url
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE pt.user_id = %s
        AND sp.scheduled_at BETWEEN %s AND %s
        ORDER BY sp.scheduled_at ASC
    """, (user_id, start_date, end_date), fetch="all")


def get_posts_for_calendar_for_admin(admin_id, start_date, end_date):
    return execute_query("""
        SELECT sp.id, sp.scheduled_at, sp.status, pt.content_text, pt.platforms, pt.media_url
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE u.admin_id = %s
        AND sp.scheduled_at BETWEEN %s AND %s
        ORDER BY sp.scheduled_at ASC
    """, (admin_id, start_date, end_date), fetch="all")


def get_posts_by_status(user_id, status):
    return execute_query("""
        SELECT sp.*, pt.content_text, pt.platforms, pt.media_url,
               sp.ai_generated, sp.trigger_type, sp.trigger_name, sp.reposted_from_id
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE pt.user_id = %s AND sp.status = %s
        ORDER BY sp.scheduled_at ASC
    """, (user_id, status), fetch="all")


def get_posts_by_status_for_admin(admin_id, status):
    return execute_query("""
        SELECT sp.*, pt.content_text, pt.platforms, pt.media_url,
               sp.ai_generated, sp.trigger_type, sp.trigger_name, sp.reposted_from_id
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        WHERE u.admin_id = %s AND sp.status = %s
        ORDER BY sp.scheduled_at ASC
    """, (admin_id, status), fetch="all")


def get_all_posts_for_superadmin(status_filter: str = None):
    where = ""
    params = []
    if status_filter:
        where = "AND sp.status = %s"
        params.append(status_filter)

    return execute_query(f"""
        SELECT
            sp.*,
            pt.content_text, pt.media_url, pt.platforms, pt.user_id,
            sp.ai_generated, sp.trigger_type, sp.trigger_name, sp.reposted_from_id,
            u.email AS user_email,
            up.brand_name, up.persona,
            pas.hr_status, pas.hr_approved_at, pas.hr_rejection_reason,
            pas.admin_status, pas.admin_approved_at, pas.admin_rejection_reason
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN post_approval_stages pas ON pas.scheduled_post_id = sp.id
        WHERE sp.status NOT IN ('scheduled')
        {where}
        ORDER BY sp.created_at DESC
    """, tuple(params) if params else None, fetch="all")

# ================================================================
# SECTION 7 — POST TARGET QUERIES
# ================================================================

def create_post_targets(scheduled_post_id, platforms: list):
    for platform in platforms:
        execute_query(
            "INSERT INTO post_targets (scheduled_post_id, platform) VALUES (%s, %s)",
            (scheduled_post_id, platform)
        )

def update_target_status(scheduled_post_id, platform, status, error_message=None):
    return execute_query("""
        UPDATE post_targets
        SET status = %s, error_message = %s, posted_at = CASE WHEN %s = 'posted' THEN NOW() ELSE NULL END
        WHERE scheduled_post_id = %s AND platform = %s
    """, (status, error_message, status, scheduled_post_id, platform))

def get_targets_for_post(scheduled_post_id):
    return execute_query(
        "SELECT * FROM post_targets WHERE scheduled_post_id = %s",
        (scheduled_post_id,), fetch="all"
    )


# ================================================================
# SECTION 8 — APPROVAL QUERIES
# ================================================================

def save_confirmation_token(post_id, token):
    return execute_query("""
        UPDATE scheduled_posts
        SET confirmation_token = %s,
            confirmation_sent_at = NOW(),
            token_used = FALSE
        WHERE id = %s
    """, (token, post_id))


def save_admin_token(post_id, token):
    return execute_query("""
        UPDATE scheduled_posts
        SET admin_token = %s,
            admin_token_used = FALSE
        WHERE id = %s
    """, (token, post_id))


def get_post_by_token(token):
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.confirmation_token = %s
        AND sp.token_used = FALSE
    """, (token,), fetch="one")

def get_post_by_admin_token(token):
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.admin_token = %s
        AND sp.admin_token_used = FALSE
    """, (token,), fetch="one")


def approve_post(post_id):
    return execute_query("""
        UPDATE scheduled_posts
        SET status = 'approved',
            approved_at = NOW(),
            token_used = TRUE
        WHERE id = %s
    """, (post_id,))

def reject_post(post_id, reason=None):
    return execute_query("""
        UPDATE scheduled_posts
        SET status = 'cancelled',
            rejection_reason = %s,
            token_used = TRUE
        WHERE id = %s
    """, (reason, post_id))


# ================================================================
# SECTION 9 — SUPERADMIN QUERIES
# ================================================================

def get_superadmin():
    return execute_query(
        "SELECT * FROM users WHERE role = 'superadmin' LIMIT 1",
        fetch="one"
    )

def create_approval_stage(post_id: int):
    return execute_query("""
        INSERT INTO post_approval_stages (scheduled_post_id)
        VALUES (%s)
        ON CONFLICT (scheduled_post_id) DO NOTHING
        RETURNING id
    """, (post_id,), fetch="one")

def get_approval_stage(post_id: int):
    return execute_query(
        "SELECT * FROM post_approval_stages WHERE scheduled_post_id = %s",
        (post_id,), fetch="one"
    )

def update_hr_approval(post_id: int, status: str, reason: str = None):
    return execute_query("""
        UPDATE post_approval_stages
        SET hr_status = %s,
            hr_approved_at = CASE WHEN %s = 'approved' THEN NOW() ELSE NULL END,
            hr_rejection_reason = %s
        WHERE scheduled_post_id = %s
    """, (status, status, reason, post_id))

def update_admin_approval(post_id: int, status: str, reason: str = None):
    return execute_query("""
        UPDATE post_approval_stages
        SET admin_status = %s,
            admin_approved_at = CASE WHEN %s = 'approved' THEN NOW() ELSE NULL END,
            admin_rejection_reason = %s
        WHERE scheduled_post_id = %s
    """, (status, status, reason, post_id))

def get_posts_awaiting_admin_approval(admin_id: int = None):
    where_clause = "AND u.admin_id = %s" if admin_id is not None else ""
    params = (admin_id,) if admin_id is not None else ()
    return execute_query(f"""
        SELECT
            sp.*,
            pt.content_text, pt.media_url, pt.platforms, pt.user_id,
            sp.ai_generated, sp.trigger_type, sp.trigger_name,
            u.email AS user_email,
            up.brand_name, up.persona,
            pas.hr_status, pas.hr_approved_at, pas.hr_rejection_reason,
            pas.admin_status
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        JOIN users u ON pt.user_id = u.id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        JOIN post_approval_stages pas ON pas.scheduled_post_id = sp.id
        WHERE sp.status = 'awaiting_admin_approval'
        AND pas.admin_status = 'pending'
        {where_clause}
        ORDER BY sp.scheduled_at ASC
    """, params, fetch="all")


def admin_final_approve(post_id: int):
    update_admin_approval(post_id, 'approved')
    return execute_query("""
        UPDATE scheduled_posts
        SET status = 'approved',
            approved_at = NOW(),
            admin_token_used = TRUE
        WHERE id = %s
    """, (post_id,))

def admin_final_reject(post_id: int, reason: str = None):
    update_admin_approval(post_id, 'rejected', reason)
    return execute_query("""
        UPDATE scheduled_posts
        SET status = 'cancelled',
            rejection_reason = %s,
            admin_token_used = TRUE
        WHERE id = %s
    """, (reason, post_id))