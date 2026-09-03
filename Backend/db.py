import sqlite3
import json
from pathlib import Path
from config import STORAGE_DIR

DB_PATH = STORAGE_DIR / "askyourdocs.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            page_count INTEGER DEFAULT 0,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chats (
            chat_id TEXT PRIMARY KEY,
            title TEXT DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_documents (
            chat_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            PRIMARY KEY (chat_id, doc_id),
            FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS collections (
            col_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS collection_documents (
            col_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            PRIMARY KEY (col_id, doc_id),
            FOREIGN KEY (col_id) REFERENCES collections(col_id) ON DELETE CASCADE,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN ingestion_status TEXT DEFAULT 'ready'")
    except sqlite3.OperationalError:
        pass
    conn.commit()

    # Auto-sync any existing documents from _registry.json into SQLite
    try:
        from config import STORAGE_DIR
        registry_path = STORAGE_DIR / "docs" / "_registry.json"
        if registry_path.exists():
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
            for doc_id, meta in registry.items():
                conn.execute(
                    "INSERT OR IGNORE INTO documents (doc_id, name, chunk_count, page_count, title, ingestion_status) VALUES (?, ?, ?, ?, ?, 'ready')",
                    (doc_id, meta.get("name", doc_id), meta.get("chunk_count", 0), meta.get("page_count", 1), meta.get("title", ""))
                )
            conn.commit()
    except Exception:
        pass

    conn.close()



# ── Document operations ──

def add_document(doc_id: str, name: str, chunk_count: int, page_count: int, title: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO documents (doc_id, name, chunk_count, page_count, title, ingestion_status) VALUES (?, ?, ?, ?, ?, 'ready')",
        (doc_id, name, chunk_count, page_count, title)
    )
    conn.commit()
    conn.close()


def set_ingestion_status(doc_id: str, status: str):
    conn = get_db()
    conn.execute("UPDATE documents SET ingestion_status = ? WHERE doc_id = ?", (status, doc_id))
    conn.commit()
    conn.close()


def get_all_documents() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_document(doc_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_document_db(doc_id: str):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
    conn.commit()
    conn.close()


# ── Chat operations ──

def create_chat(chat_id: str, title: str = "New Chat", doc_ids: list[str] | None = None) -> dict:
    conn = get_db()
    conn.execute("INSERT INTO chats (chat_id, title) VALUES (?, ?)", (chat_id, title))
    if doc_ids:
        conn.executemany(
            "INSERT OR IGNORE INTO chat_documents (chat_id, doc_id) VALUES (?, ?)",
            [(chat_id, did) for did in doc_ids]
        )
    conn.commit()
    conn.close()
    return {"chat_id": chat_id, "title": title}


def get_all_chats() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT c.*, COUNT(m.id) as msg_count FROM chats c LEFT JOIN messages m ON c.chat_id = m.chat_id GROUP BY c.chat_id ORDER BY c.updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_chat_title(chat_id: str, title: str):
    conn = get_db()
    conn.execute("UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (title, chat_id))
    conn.commit()
    conn.close()


def delete_chat(chat_id: str):
    conn = get_db()
    conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


def get_chat_documents(chat_id: str) -> list[str]:
    conn = get_db()
    rows = conn.execute("SELECT doc_id FROM chat_documents WHERE chat_id = ?", (chat_id,)).fetchall()
    conn.close()
    return [r["doc_id"] for r in rows]


# ── Message operations ──

def add_message(chat_id: str, role: str, content: str, sources: list[dict] | None = None) -> int:
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (chat_id, role, content, sources) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, json.dumps(sources) if sources else None)
    )
    conn.execute("UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (chat_id,))
    msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return msg_id


def get_messages(chat_id: str) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_messages(chat_id: str):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


# ── Collection operations ──

def create_collection(col_id: str, name: str) -> dict:
    conn = get_db()
    conn.execute("INSERT INTO collections (col_id, name) VALUES (?, ?)", (col_id, name))
    conn.commit()
    conn.close()
    return {"col_id": col_id, "name": name}


def get_all_collections() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT c.*, COUNT(cd.doc_id) as doc_count FROM collections c LEFT JOIN collection_documents cd ON c.col_id = cd.col_id GROUP BY c.col_id ORDER BY c.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_doc_to_collection(col_id: str, doc_id: str):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO collection_documents (col_id, doc_id) VALUES (?, ?)", (col_id, doc_id))
    conn.commit()
    conn.close()


def remove_doc_from_collection(col_id: str, doc_id: str):
    conn = get_db()
    conn.execute("DELETE FROM collection_documents WHERE col_id = ? AND doc_id = ?", (col_id, doc_id))
    conn.commit()
    conn.close()


def get_collection_documents(col_id: str) -> list[str]:
    conn = get_db()
    rows = conn.execute("SELECT doc_id FROM collection_documents WHERE col_id = ?", (col_id,)).fetchall()
    conn.close()
    return [r["doc_id"] for r in rows]


def delete_collection(col_id: str):
    conn = get_db()
    conn.execute("DELETE FROM collections WHERE col_id = ?", (col_id,))
    conn.commit()
    conn.close()


# Auto-init on import
init_db()


# ── User operations ──

def create_user(user_id: str, email: str, password_hash: str, salt: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO users (user_id, email, password_hash, salt) VALUES (?, ?, ?, ?)",
        (user_id, email, password_hash, salt)
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Feedback operations ──

def add_feedback(chat_id: str, message_id: int, rating: str):
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            rating TEXT NOT NULL CHECK(rating IN ('up', 'down')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id, message_id) REFERENCES messages(chat_id, id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "INSERT OR REPLACE INTO feedback (chat_id, message_id, rating) VALUES (?, ?, ?)",
        (chat_id, message_id, rating)
    )
    conn.commit()
    conn.close()
