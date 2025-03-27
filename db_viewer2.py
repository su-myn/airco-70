import sqlite3

# Connect to the database
conn = sqlite3.connect('instance/propertyhub.db')
cursor = conn.cursor()

# Get list of all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("Tables in the database:")
for table in tables:
    print(table[0])

# Try to query each of the tables from your models
table_names = ['user', 'complaint', 'repair', 'replacement']

for table_name in table_names:
    print(f"\n--- {table_name.upper()} TABLE ---")
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Get column names
        column_names = [description[0] for description in cursor.description]

        # Print header
        print(" | ".join(column_names))
        print("-" * (sum(len(col) for col in column_names) + 3 * (len(column_names) - 1)))

        # Print rows
        for row in rows:
            print(" | ".join(str(item) for item in row))

        print(f"\nTotal rows: {len(rows)}")
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")

conn.close()