# Section 1: Connection Pool
# Section 2: Schema (All CREATE TABLE)
# Section 3: User Queries
# Section 4: Social Account Queries
# Section 5: Post Template Queries
# Section 6: Scheduled Post Queries
# Section 7: Post Target Queries
# Section 8: Approval Queries

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
                    created_at      TIMESTAMP DEFAULT NOW()
                );
            """)
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
                    token_used              BOOLEAN DEFAULT FALSE,
                    status                  VARCHAR(50) DEFAULT 'scheduled',
                    approved_at             TIMESTAMP,
                    rejection_reason        TEXT,
                    created_at              TIMESTAMP DEFAULT NOW()
                );
            """)
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
                    event_type   VARCHAR(50),     -- national, religious, global
                    raw_data     JSONB,
                    fetched_at   TIMESTAMP DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS trends_cache (
                    id           SERIAL PRIMARY KEY,
                    country_code VARCHAR(5),
                    platform     VARCHAR(50),     -- google, instagram, general
                    topic        VARCHAR(200),
                    score        FLOAT,           -- how trending (higher = more trending)
                    raw_data     JSONB,
                    fetched_at   TIMESTAMP DEFAULT NOW()
                );
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

def create_user(email: str, password_hash: str):
    return execute_query(
        "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
        (email, password_hash),
        fetch="one"
    )

def get_user_by_email(email: str):
    return execute_query(
        "SELECT * FROM users WHERE email = %s",
        (email,),
        fetch="one"
    )

def get_user_by_id(user_id: int):
    return execute_query(
        "SELECT id, email, timezone, created_at FROM users WHERE id = %s",
        (user_id,),
        fetch="one"
    )


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

def create_scheduled_post(template_id, scheduled_at):
    return execute_query(
        "INSERT INTO scheduled_posts (template_id, scheduled_at) VALUES (%s, %s) RETURNING id",
        (template_id, scheduled_at), fetch="one"
    )

def get_post_by_id(post_id):
    return execute_query("""
        SELECT sp.*, pt.content_text, pt.media_url, pt.platforms, pt.user_id
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.id = %s
    """, (post_id,), fetch="one")

def get_posts_due_for_confirmation():
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.status = 'scheduled'
        AND pt.status = 'active'
        AND sp.scheduled_at - INTERVAL '30 minutes' <= NOW()
        AND sp.scheduled_at > NOW()
    """, fetch="all")

def get_expired_awaiting_posts():
    """Posts still awaiting approval but scheduled time has passed"""
    return execute_query("""
        SELECT * FROM scheduled_posts
        WHERE status = 'awaiting_approval'
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

def get_posts_by_status(user_id, status):
    return execute_query("""
        SELECT sp.*, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE pt.user_id = %s AND sp.status = %s
        ORDER BY sp.scheduled_at ASC
    """, (user_id, status), fetch="all")


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

def get_post_by_token(token):
    return execute_query("""
        SELECT sp.*, pt.user_id, pt.content_text, pt.platforms
        FROM scheduled_posts sp
        JOIN post_templates pt ON sp.template_id = pt.id
        WHERE sp.confirmation_token = %s
        AND sp.token_used = FALSE
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