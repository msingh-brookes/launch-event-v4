import os
import psycopg2

def print_table(table_name):
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]

    print(f"\n--- {table_name} ---")
    print(colnames)
    for row in rows:
        print(row)

    cur.close()
    conn.close()

if __name__ == "__main__":
    for table in ["users", "poll_votes", "interests", "questions"]:
        try:
            print_table(table)
        except Exception as e:
            print(f"Error printing {table}: {e}")
