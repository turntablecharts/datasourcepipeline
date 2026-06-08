import os
from dotenv import load_dotenv

load_dotenv()

class EnvConstants:
    FTP_HOST = '195.35.49.228'
    FTP_USER =  'u251061335.turntable'
    FTP_PASS = 'Turntable2020.'
    GPG_PASSPHRASE = 'q#HMPrDK&h4J9@J%dHbH3'
    DB_HOST=os.getenv('DB_HOST')
    DB_USER=os.getenv('DB_USER')
    DB_PASSWORD=os.getenv('DB_PASSWORD')
    DB_PORT=os.getenv('DB_PORT')
    DB_NAME=os.getenv('DB_NAME')