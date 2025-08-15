from crypto import sigma
import enclave.attest as attest
import skrecovery.helpers as helpers
import hashlib

class EnclaveRes:
    def __init__(self) -> None:
        self.req_type = None
        self.payload = {}
        self.time_taken = 0
        self.is_removed = False
        self.is_valid_ctx = False
        self.signature = None
        self.error = None
        self.gatt = None
    
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
            'signature': sigma.stringify(self.signature),
            'payload': self.payload,
            'is_valid_ctx': self.is_valid_ctx,
            'is_removed': self.is_removed,
            'time_taken': self.time_taken,
            'error': self.error,
            'gatt': self.gatt
        }
        
    def sign(self, sk: str | sigma.PrivateKey):
        self.signature = sigma.sign(sk, self.payload)

    def attest_res(self):
        data: bytes = bytes(helpers.stringify(self.serialize()), 'utf-8')
        user_data = hashlib.sha256(data).digest()
        self.gatt = attest.get_attestation_document(user_data=user_data)
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
        return attest.validate(
            attestation=bytes.fromhex(self.gatt),
            expected_user_data=user_data
        )

    @staticmethod
    def deserialize(data: dict):
        res = EnclaveRes()
        res.req_type = data.get('type', None)
        res.payload = data.get('payload', {})
        res.is_removed = bool(data.get('is_removed', False))
        res.is_valid_ctx = bool(data.get('is_valid_ctx', False))
        res.signature = sigma.import_signature(data.get('signature')) if data.get('signature') is not None else None
        res.time_taken = data.get('time_taken', 0)
        res.error = data.get('error', None)
        res.gatt = data.get('gatt')
        return res
    
    @staticmethod
    def error(code: int, message: str) -> 'EnclaveRes':
        res = EnclaveRes()
        res.error = {
            'code': code,
            'message': message
        }
        return res
