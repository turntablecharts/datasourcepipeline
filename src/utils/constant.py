import os
from dotenv import load_dotenv

load_dotenv()

class EnvConstants:
    DB_HOST=os.getenv('DB_HOST')
    DB_USER=os.getenv('DB_USER')
    DB_PASSWORD=os.getenv('DB_PASSWORD')
    DB_PORT=os.getenv('DB_PORT')
    DB_NAME=os.getenv('DB_NAME')
    FTP_HOST=os.getenv('FTP_HOST')
    FTP_USER=os.getenv('FTP_USER')
    FTP_PASS=os.getenv('FTP_PASS')
    GPG_PASSPHRASE=os.getenv('GPG_PASSPHRASE')
