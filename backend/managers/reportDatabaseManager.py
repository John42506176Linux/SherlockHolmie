from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from managers.tunnelManager import TunnelManager
import os
from models.report_models import Base, Report, Insight, PainPoint, Persona
import logging.handlers


log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

db_username = os.getenv('SMALL_DB_USERNAME')
db_password = os.getenv('SMALL_DB_PASSWORD')
db_host = os.getenv('SMALL_DB_HOST')
db_port = os.getenv('DB_PORT')
db_database = os.getenv('SMALL_DB_DATABASE')


def generate_connection_string(host, port):
    return f"postgresql://{db_username}:{db_password}@{host}:{port}/{db_database}"

class DatabaseManager:
    def __init__(self):
        self.connection_string = ""
        if os.getenv('ENV') != 'PROD':
            tunnel_manager = TunnelManager()
            tunnel_manager.start_tunnel()
            self.connection_string = generate_connection_string('127.0.0.1', tunnel_manager.server.local_bind_port)
        else:
            self.connection_string = generate_connection_string(db_host, db_port)
        self.engine = create_engine(self.connection_string, pool_size=10)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def initialize_database(self):
        log.info("Starting connecting")
        with self.engine.connect() as cur:
            log.info("Connecting to postgres")
            log.info("Create db call")
            Base.metadata.create_all(self.engine, checkfirst=True)
            log.info("Meta data created")
            
    def close(self):
        self.db.rollback()
        self.db.close()