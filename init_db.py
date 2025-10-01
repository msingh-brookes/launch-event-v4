import os
import psycopg2
from print_db import print_table

def init_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set. Configure it in your environment.")

    # Ensure psycopg2 gets correct format
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    conn = psycopg2.connect(db_url, sslmode="require")
    cur = conn.cursor()

    # Drop and recreate tables (safe for dev)
    cur.execute("""
        DROP TABLE IF EXISTS poll_votes;
        DROP TABLE IF EXISTS interests;
        DROP TABLE IF EXISTS questions;
        DROP TABLE IF EXISTS users;
        """)

    # Create users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        organisation TEXT NOT NULL,
        password TEXT,         -- still kept for admins
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create questions table with 'answered' field
    cur.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        question TEXT NOT NULL,
        recipient TEXT NOT NULL,
        answered INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create a table for storing poll answers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS poll_votes (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        option TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create interests table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interests (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        phrase TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)



    # Seed data
    cur.execute("INSERT OR IGNORE INTO users (first_name, last_name, organisation, password, is_admin) VALUES (?, ?, ?, ?, ?)",
                ("admin","","", "DPRIN1234", 1))
    #cur.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)", ("alice", "1234", 0))
    #cur.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)",("bob", "1234", 0))

    conn.commit()
    cur.close()
    conn.close()
    print_table(conn, "poll_votes")
    print_table(conn, "users")

#print("Regular user: alice / 1234")
#print("Regular user: bob / 1234")

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
    print("Admin user: admin / DPRIN1234")

