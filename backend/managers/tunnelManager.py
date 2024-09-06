from sshtunnel import SSHTunnelForwarder
import os
from dotenv import load_dotenv

class TunnelManager:
    def __init__(self):
        load_dotenv(override=True)
        self.server = None
        self.SSH_HOST = os.getenv('SSH_HOST')
        self.SSH_PORT = int(os.getenv('SSH_PORT', 22))
        self.SSH_USERNAME = os.getenv('SSH_USERNAME')
        self.SSH_PASSWORD = os.getenv('SSH_PASSWORD')
        self.REMOTE_BIND_ADDRESS = os.getenv('DB_HOST')
        self.REMOTE_BIND_PORT = int(os.getenv('DB_PORT'))
        self.SSH_PRIVATE_KEY = os.getenv('SSH_PRIVATE_KEY')

    def start_tunnel(self):
        self.server = SSHTunnelForwarder(
            (self.SSH_HOST, self.SSH_PORT),
            ssh_username=self.SSH_USERNAME,
            ssh_password=self.SSH_PASSWORD,
            ssh_pkey=self.SSH_PRIVATE_KEY,
            remote_bind_address=(self.REMOTE_BIND_ADDRESS, self.REMOTE_BIND_PORT),
        )
        self.server.start()
        print(f"Tunnel established from {self.server.local_bind_address}:{self.server.local_bind_port} to {self.REMOTE_BIND_ADDRESS}:{self.REMOTE_BIND_PORT}")

    def stop_tunnel(self):
        if self.server:
            self.server.stop()
            print("Tunnel closed")
