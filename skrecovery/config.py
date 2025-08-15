from os import getenv
from dotenv import load_dotenv
from collections import namedtuple

load_dotenv(override=True)

def env(envname, default=""):
    value = getenv(envname)
    return value or default

DB_HOST = env("DB_HOST", "127.0.0.1")
DB_PORT = env("DB_PORT", 27017)
DB_NAME = env("DB_NAME", "skrec")
DB_USER = env("DB_USER", "root")
DB_PASS = env("DB_PASS", "secret")

ENV_FILE = env("ENV_FILE")

# Hyperledger Fabric
NUM_FAULTS = int(env("NUM_FAULTS", 2))
NUM_PEERS = int(env("NUM_PEERS", 25))
NUM_ORDERERS = int(env("NUM_ORDERERS", 7))
NUM_ENDORSEMENTS = int(env("NUM_ENDORSEMENTS", 15))
MAX_TXS_PER_BLOCK = int(env("MAX_TXS_PER_BLOCK", 500))
PREFERRED_MAX_BLOCK_SIZE_KB = int(env("PREFERRED_MAX_BLOCK_SIZE_KB", 2 * 1024))

T_OPEN = int(env("T_OPEN", 15)) # 30 seconds
T_WAIT = int(env("T_CHAL", 302400)) # 1 week but will not be included in permission
T_CHAL = int(env("T_CHAL", 300)) # 10 minutes
T_OPEN_BUFFER = int(env("T_OPEN_BUFFER", 0))

ORDER_SERVICE_CONFIG = {
    "NUM_FAULTS": NUM_FAULTS,
    "NUM_PEERS": NUM_PEERS,
    "NUM_ORDERERS": NUM_ORDERERS,
    "NUM_ENDORSEMENTS": NUM_ENDORSEMENTS,
    "MAX_TXS_PER_BLOCK": MAX_TXS_PER_BLOCK
}

USE_VSOCK = bool(int(env("USE_VSOCK", 1)))
VSOCK_HOST = int(env("VSOCK_HOST", 16))
VSOCK_PORT = int(env("VSOCK_PORT", 5005))
VSOCK_ENV = env('VSOCK_ENV', 'nitro')

def is_nitro_env():
    return VSOCK_ENV == 'nitro'

AWS_NITRO_ROOT_CERT_PEM = env("AWS_NITRO_ROOT_CERT_PEM")