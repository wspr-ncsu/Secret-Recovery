import traceback
from enclave.response import EnclaveRes
from skrecovery.helpers import parse_json, stringify
from skrecovery import config
from enclave.requests import EnclaveReqType, StoreReq, RetrieveReq, RemoveReq, RecoverReq, VerifyCiphertextReq, TEEReq

def parse_req(req: dict) -> StoreReq | RetrieveReq | RemoveReq | RecoverReq | VerifyCiphertextReq:
    req_type: str = req.get('type', None)
    if req_type == EnclaveReqType.STORE.value:
        return StoreReq(req)
    elif req_type == EnclaveReqType.RETRIEVE.value:
        return RetrieveReq(req)
    elif req_type == EnclaveReqType.REMOVE.value:
        return RemoveReq(req)
    elif req_type == EnclaveReqType.RECOVER.value:
        return RecoverReq(req)
    elif req_type == EnclaveReqType.VERIFY_CIPHERTEXT.value:
        return VerifyCiphertextReq(req)
    else:
        raise ValueError(f"Invalid request type: {req_type}")

def run(req: dict | str | bytes) -> dict | str:
    if type(req) == bytes:
        req = req.decode()
        
    if type(req) == str:
        req = parse_json(req)
    
    try:
        req: TEEReq = parse_req(req)
        res: EnclaveRes = req.process_req()
        if config.is_nitro_env():
            res.attest_res()
    except Exception as e:
        traceback.print_exc()
        res: EnclaveRes = EnclaveRes.error(code=422, message=str(e))
        
    return stringify(res.serialize())