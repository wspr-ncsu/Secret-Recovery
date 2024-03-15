from ..crypto import ciphers, ec_group, sigma
from . import chain
from enum import Enum
from fabric.transaction import Signer

class EnclaveReqType(Enum):
    STORE = 'store'
    RECOVER = 'recover'
    REGISTER = 'register'
    VERIFY_CIPHERTEXT = 'verify_ciphertext'
    
class EnclaveResponse:
    req_type: EnclaveReqType = None
    signature: sigma.Signature = None
    payload: dict = None
    is_valid_ctx: bool = False
    
    def verify(self, vk: str | sigma.PublicKey):
        return sigma.verify(vk, self.payload, self.signature)


msk, mvk = None, None
retKs = {}
ctxs = {}

def install():
    global msk, mvk
    if msk is None or mvk is None:
        msk, mvk = sigma.keygen()
    
def getpk():
    return mvk
    
def store(A, vk_client: str):
    global retKs
    vk_client = sigma.stringify(vk_client)
    b, B = ec_group.random_DH()
    retKs[vk_client] = b * A
    
    sig = sigma.sign(msk, f"{vk_client}|{A.hex()}|{B.hex()}")
    
    return B, vk_client, sig
    

def verify_ciphertext(vk_client, perm_info, aes_ctx):
    vk_client = sigma.stringify(vk_client)
    msg = ciphers.aes_dec(retKs[vk_client], aes_ctx)
    perm_info_prime, secret = msg.split(b'|')
    return perm_info_prime == perm_info

def remove(vk_client, perm_info, sig):
    remove_msg = b"remove" + b"|" + perm_info
    
    if not sigma.verify(vk_client, remove_msg, sig):
        raise Exception("Invalid signature")
    
    retKs[sigma.stringify(vk_client)] = None
    
    sig = sigma.sign(msk, b"removed" + b'|' + perm_info + b"|" + bytes(sig))
    
    return sig


recovery_data = {}

valid_windows = {
    'chal_window_c': False,
    'chal_window_req': False,
    'com_window': False
}

previous_hashes = {
    'chal_window_c': None,
    'chal_window_req': None,
    'com_window': None
}

def begin_recovery(data):
    global recovery_data
    recovery_data = data
    
    # verify server signature
    # sigma.verify(svk, b"recover", ssig)
    # sigma.verify(svk, b"recover", lsig)
    
def end_recovery():
    rec_pubk = recovery_data['pubk']
    rec_aes_ctx = recovery_data['aes_ctx']
    rec_req = recovery_data['req']
    rec_perm_info = recovery_data['perm_info']
    rec_cvk = recovery_data['cvk']
    
    req_prime = b"recover" + b"|" + rec_pubk.export_key()
    # print(req_prime, rec_req)
    assert verify_perm() and rec_req == req_prime
    
    retK = retKs[sigma.stringify(rec_cvk)]
    plaintext = ciphers.aes_dec(retK, rec_aes_ctx)
    splited_plaintext = plaintext.split(b'|')
    
    assert splited_plaintext[0] == rec_perm_info
    
    rsa_ctx = ciphers.rsa_enc(pubKey=rec_pubk, data=plaintext)
    sig = sigma.sign(msk, ciphers.rsa_ctx_to_bytes(rsa_ctx) + b'|' + rec_perm_info)
    
    reset_windows()
    
    return rsa_ctx, sig

def reset_windows():
    valid_windows['chal_window_c'] = False
    valid_windows['chal_window_req'] = False
    valid_windows['com_window'] = False
    
    previous_hashes['chal_window_c'] = None
    previous_hashes['chal_window_req'] = None
    previous_hashes['com_window'] = None
    
    
def verify_window(block, window_name):
    # No need to validate, since we are not using the chain
    if valid_windows[window_name] is False and previous_hashes[window_name] is not None:
        return False
    
    if not chain.validate_block(block):
        valid_windows[window_name] = False
        previous_hashes[window_name] = block['hash']
        return
    
    if previous_hashes[window_name] is None:
        previous_hashes[window_name] = block['hash']
        valid_windows[window_name] = True
        return
    else:
        if previous_hashes[window_name] == block['prev_hash']:
            previous_hashes[window_name] = block['hash']
            valid_windows[window_name] = True
            return
        else:
            valid_windows[window_name] = False
            previous_hashes[window_name] = block['hash']
            return False
        
def verify_chal_window_c(block):
    # print(recovery_data)
    verify_window(block, 'chal_window_c')
    for i in range(len(block['data'])):
        sigma.verify(recovery_data['svk'], b"recover", recovery_data['ssig']) # sim chalwindow check
        sigma.verify(recovery_data['svk'], b"recover", recovery_data['ssig']) # sim denial check

def verify_chal_window_req(block):
    verify_window(block, 'chal_window_req')
    for i in range(len(block['data'])):
        sigma.verify(recovery_data['svk'], b"recover", recovery_data['ssig']) # sim chalwindow check
        sigma.verify(recovery_data['svk'], b"recover", recovery_data['ssig']) # sim denial check

def verify_com_window(block):
    verify_window(block, 'com_window')

def set_client_retK(vk_client, retK):
    global retKs
    retKs[sigma.stringify(vk_client)] = retK

def set_client_secret(vk_client, data):
    ctxs[sigma.stringify(vk_client)] = data
    
def sign(msg):
    return sigma.sign(msk, msg)

def verify_perm():
    return valid_windows['chal_window_c'] and valid_windows['chal_window_req'] and valid_windows['com_window']