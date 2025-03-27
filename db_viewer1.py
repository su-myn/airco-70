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
    print(f"\nAttempting to query {table_name} table:")
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Get column names
        column_names = [description[0] for description in cursor.description]
        print(f"Columns: {column_names}")

        # Print first few rows (up to 5)
        print("Data:")
        for i, row in enumerate(rows):
            print(row)
            if i >= 4:  # Print only first 5 rows
                print(f"... and {len(rows) - 5} more rows")
                break
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")

conn.close()