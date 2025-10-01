import sqlite3

DB_PATH = "archive/users.db"

def print_table(conn, table_name):
    print(f"\n--- {table_name.upper()} ---")
    try:
        cur = conn.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        col_names = [description[0] for description in cur.description]

        if not rows:
            print("(no rows)")
            return

        # Print header
        print(" | ".join(col_names))
        print("-" * 50)

        # Print rows
        for row in rows:
            print(" | ".join(str(value) if value is not None else "" for value in row))

    except sqlite3.OperationalError as e:
        print(f"Table {table_name} does not exist. ({e})")

def main():
    conn = sqlite3.connect(DB_PATH)

    for table in ["users", "questions", "poll_votes", "interests"]:
        print_table(conn, table)

    conn.close()

if __name__ == "__main__":
    main()
