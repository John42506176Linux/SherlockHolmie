import psycopg2
from psycopg2 import sql

# Replace these with your database credentials
DB_NAME = 'RedditDataBase'
DB_USER = 'admin_user'
DB_PASSWORD = '0UySg8TdhOsfm_rHciAkgA=2e0aaYZ'
DB_HOST = 'databasestack-auroraserverlessb4af3148-syakp7htzsbg.cluster-c10w0amci5vy.us-west-2.rds.amazonaws.com'  # e.g., 'your-db-instance.cxyz12345678.us-east-1.rds.amazonaws.com'
DB_PORT = '5432'  # Default PostgreSQL port

try:
    # Connect to your PostgreSQL database
    connection = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    
    # Create a cursor object
    cursor = connection.cursor()
    
    # Execute a test query
    cursor.execute("SELECT version();")
    
    # Fetch and print the result of the query
    db_version = cursor.fetchone()
    print(f"Connected to PostgreSQL database, version: {db_version}")
    
    # Close the cursor and connection
    cursor.close()
    connection.close()
    
except Exception as error:
    print(f"Error connecting to PostgreSQL database: {error}")
