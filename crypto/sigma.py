import secrets
from skrecovery import helpers
from blspy import BasicSchemeMPL as sigma, PrivateKey, G1Element as PublicKey, G2Element as Signature

def keygen():
    privkey = sigma.key_gen(secrets.token_bytes(32))
    return (privkey, privkey.get_g1())

def sign(privkey: PrivateKey, message) -> Signature:
    privkey = import_priv_key(privkey)
    message = msg_to_bytes(message)
    return sigma.sign(privkey, message)

def verify(pubkey: PublicKey, message, signature: Signature) -> bool:
    message = msg_to_bytes(message)
    pubkey = import_pub_key(pubkey)
    signature = import_signature(signature)
    return sigma.verify(pubkey, message, signature)

def stringify(key): 
    if key is None:
        return None
    
    if type(key) == str:
        return key
    
    return bytes(key).hex()

def msg_to_bytes(msg):
    if type(msg) == dict:
        msg = helpers.stringify(msg)
        
    if type(msg) == str:
        return msg.encode()
    
    return msg

def import_signature(sig: str) -> Signature:
    if isinstance(sig, Signature):
        return sig
    
    if isinstance(sig, str):
        sig = bytes.fromhex(sig)
    
    return Signature.from_bytes(sig)

def import_priv_key(privkey) -> PrivateKey:
    if isinstance(privkey, PrivateKey):
        return privkey
    
    if isinstance(privkey, str):
        privkey = bytes.fromhex(privkey)
    
    return PrivateKey.from_bytes(privkey)

def import_pub_key(pubkey: str) -> PublicKey:
    if isinstance(pubkey, PublicKey):
        return pubkey
    
    if isinstance(pubkey, str):
        pubkey = bytes.fromhex(pubkey)
    
    return PublicKey.from_bytes(pubkey)

def parse_keys(keystr: str, imp = True):
    privkey, pubkey = keystr.split(':')
    
    if not imp:
        return (privkey, pubkey)
    
    return (import_priv_key(privkey), import_pub_key(pubkey))

def export_keys(privkey: PrivateKey, pubkey: PublicKey):
    return f"{stringify(privkey)}:{stringify(pubkey)}"