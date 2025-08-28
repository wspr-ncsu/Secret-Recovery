from crypto import sigma
import enclave.attest as attest
from skrecovery import helpers, config
import hashlib

class EnclaveRes:
    def __init__(self) -> None:
        self.req_type = None
        self.payload = {}
        self.time_taken = 0
        self.is_removed = False
        self.is_valid_ctx = False
        self.error = None
        self.gatt = None
        self.lvk = None
    
    def verify(self, vk: str | sigma.PublicKey):
        return self.validate_attest()
    
    def serialize(self):
        if self.error is not None:
            return {
                'type': self.req_type,
                'error': self.error,
                'gatt': self.gatt
            }
            
        return {
            'type': self.req_type,
            'payload': self.payload,
            'is_valid_ctx': self.is_valid_ctx,
            'is_removed': self.is_removed,
            'time_taken': self.time_taken,
            'error': self.error,
            'gatt': self.gatt,
            'lvk': self.lvk
        }
        
    def local_sign(self, message: bytes):
        sig = sigma.sign(attest.privateKey, message)
        return bytes(sig)
    
    def local_verify(self, message, signature):
        return sigma.verify(
            pubkey=self.lvk,
            message=message,
            signature=signature
        )

    def attest_res(self):
        self.lvk = attest.publicKey.hex()
        data: bytes = bytes(helpers.stringify(self.serialize()), 'utf-8')
        user_data = hashlib.sha256(data).digest()

        if config.is_nitro_env():
            self.gatt = attest.get_attestation_document(user_data=user_data)
        else:
            self.gatt = self.local_sign(user_data)

        self.gatt = self.gatt.hex()

    def attest_to_json(self):
        if not self.gatt:
            return None
        return attest.attestation_to_json(bytes.fromhex(self.gatt))

    def validate_attest(self):
        data = self.serialize()
        data['gatt'] = None
        data: bytes = bytes(helpers.stringify(data), 'utf-8')
        user_data = hashlib.sha256(data).digest()
        attestation = bytes.fromhex(self.gatt)
        
        if config.is_nitro_env():
            return attest.validate(
                attestation=attestation,
                expected_user_data=user_data
            )
        else:
            return self.local_verify(
                message=user_data, 
                signature=attestation
            )

    @staticmethod
    def deserialize(data: dict):
        res = EnclaveRes()
        res.req_type = data.get('type', None)
        res.payload = data.get('payload', {})
        res.is_removed = bool(data.get('is_removed', False))
        res.is_valid_ctx = bool(data.get('is_valid_ctx', False))
        res.time_taken = data.get('time_taken', 0)
        res.error = data.get('error', None)
        res.gatt = data.get('gatt')
        res.lvk = data.get('lvk')
        return res
    
    @staticmethod
    def error(code: int, message: str) -> 'EnclaveRes':
        res = EnclaveRes()
        res.error = {
            'code': code,
            'message': message
        }
        return res
