import sqlite3

DB_FILE = "expenses.db"

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

# Check if column already exists
c.execute("PRAGMA table_info(expenses)")
columns = [column[1] for column in c.fetchall()]

if "type" not in columns:
    c.execute("ALTER TABLE expenses ADD COLUMN type TEXT DEFAULT 'expense'")
    print("Column 'type' added successfully!")
else:
    print("Column 'type' already exists.")

conn.commit()
conn.close()
