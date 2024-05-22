import psycopg2
import logging.handlers
from dotenv import load_dotenv
import os
from psycopg2 import sql
from tunnelManager import tunnel_manager
from datetime import datetime

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()

db_username = os.getenv('DB_USERNAME')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_database = os.getenv('DB_DATABASE')

# Connect to the database and create the extension
def generate_connection_string(host, port):
    return f"postgresql://{db_username}:{db_password}@{host}:{port}/{db_database}"

connection_string = ""
tunnel_manager.start_tunnel()
connection_string = generate_connection_string('127.0.0.1', tunnel_manager.server.local_bind_port)

# Connect to the PostgreSQL database
with psycopg2.connect(connection_string) as conn:
    with conn.cursor() as cur:

        # Define your query
        query = sql.SQL("""
            SELECT subreddit_name, permalink, body
            FROM reddit_posts
            WHERE fts @@ to_tsquery('Super.com')
            ORDER BY created_utc DESC
            LIMIT 1000;
        """)

        # Execute the query
        cur.execute(query)

        # Fetch all the rows
        rows = cur.fetchall()

        # Print the rows
        for row in rows:
            print(row)

# The connection will be closed automatically after exiting the 'with' block
