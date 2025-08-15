import os
import time
import re
import json
import hashlib
import traceback
from functools import lru_cache
from typing import Union, Optional, List
import datetime as dt

import cbor2
import aws_nsm_interface
from crypto import sigma
import skrecovery.config as config

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils, rsa, padding as asy_padding
from cryptography.hazmat.primitives.asymmetric import utils as asn1_utils

# ---------------------------------------------------------------------------
# Key management (BLS app key you want NSM to bind)
# ---------------------------------------------------------------------------

publicKey: Optional[bytes] = None
privateKey: Optional[bytes] = None

def init():
    """
    Initialize application keys. Expects sigma.keygen() -> (sk, pk).
    Ensure publicKey is raw bytes suitable for attestation binding.
    """
    global publicKey, privateKey
    if publicKey and privateKey:
        return
    sk, pk = sigma.keygen()
    privateKey = bytes(sk)
    publicKey = bytes(pk)


# ---------------------------------------------------------------------------
# Attestation acquisition
# ---------------------------------------------------------------------------

def get_attestation_document(nonce: Optional[bytes] = None, user_data: Optional[bytes] = None) -> Optional[bytes]:
    """
    Request an attestation document from the NSM device, binding `publicKey`.
    """
    nsm_fd = None
    try:
        if not isinstance(publicKey, (bytes, bytearray)):
            raise TypeError("publicKey must be raw bytes for attestation binding")

        nsm_fd = os.open("/dev/nsm", os.O_RDWR)
        attestation_doc = aws_nsm_interface.get_attestation_doc(
            nsm_fd,
            public_key=publicKey,   # DO NOT stringify
            nonce=nonce,
            user_data=user_data
        )
        return attestation_doc["document"]
    except Exception as e:
        print(f"Error obtaining attestation document: {e}")
        traceback.print_exc()
        return None
    finally:
        if nsm_fd is not None:
            os.close(nsm_fd)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def to_pinned_root_spki_sha256(pem_or_var: Union[str, bytes], as_hex: bool = False) -> Union[bytes, str]:
    """
    Extract the PEM certificate from the input string/bytes, compute SHA-256 over its SPKI,
    and return the digest (bytes by default, hex string if as_hex=True).
    """
    if isinstance(pem_or_var, bytes):
        text = pem_or_var.decode("ascii", errors="ignore")
    else:
        text = pem_or_var

    m = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", text, re.S)
    if not m:
        raise ValueError("No PEM certificate found in input.")

    cert = x509.load_pem_x509_certificate(m.group(0).encode("ascii"))
    spki = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    digest = hashlib.sha256(spki).digest()
    return digest.hex() if as_hex else digest


def _verify_signed_by(child: x509.Certificate, issuer: x509.Certificate) -> bool:
    """Verify that `issuer` signed `child`."""
    pk = issuer.public_key()
    try:
        if isinstance(pk, ec.EllipticCurvePublicKey):
            pk.verify(child.signature, child.tbs_certificate_bytes,
                      ec.ECDSA(child.signature_hash_algorithm))
        elif isinstance(pk, rsa.RSAPublicKey):
            pk.verify(child.signature, child.tbs_certificate_bytes,
                      asy_padding.PKCS1v15(), child.signature_hash_algorithm)
        else:
            return False
        return True
    except Exception:
        return False


def _spki_sha256(cert: x509.Certificate) -> bytes:
    spki = cert.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(spki).digest()


def _cert_validity_window_utc(cert: x509.Certificate):
    """Return (not_before, not_after) as timezone-aware UTC datetimes."""
    try:
        # cryptography >= 41
        return cert.not_valid_before_utc, cert.not_valid_after_utc
    except AttributeError:
        # Older cryptography: fall back to naive values, treat as UTC
        nbf = cert.not_valid_before
        naf = cert.not_valid_after
        if nbf.tzinfo is None:
            nbf = nbf.replace(tzinfo=dt.timezone.utc)
        if naf.tzinfo is None:
            naf = naf.replace(tzinfo=dt.timezone.utc)
        return nbf, naf


# ---------------------------------------------------------------------------
# Fast COSE helpers (avoid pycose overhead)
# ---------------------------------------------------------------------------

# Canonical protected header bstr for {1: ES384} (map(1){alg:-35})
_COSE_ES384_PROTECTED = b"\xA1\x01\x38\x22"

def _encode_cbor_bstr(b: bytes) -> bytes:
    L = len(b)
    if L < 24:
        return bytes([0x40 | L]) + b
    elif L <= 0xFF:
        return b"\x58" + bytes([L]) + b
    elif L <= 0xFFFF:
        return b"\x59" + L.to_bytes(2, "big") + b
    elif L <= 0xFFFFFFFF:
        return b"\x5A" + L.to_bytes(4, "big") + b
    else:
        return b"\x5B" + L.to_bytes(8, "big") + b

def _make_sig_structure(protected_bstr: bytes, payload_bstr: bytes) -> bytes:
    # Sig_structure = ["Signature1", protected, external_aad="", payload]
    # 0x84 = array(4), 0x6A = tstr(len=10) "Signature1", 0x40 = bstr("")
    return (
        b"\x84" +
        b"\x6aSignature1" +
        _encode_cbor_bstr(protected_bstr) +
        b"\x40" +
        _encode_cbor_bstr(payload_bstr)
    )

def _cose_ecdsa_sig_to_der(sig: bytes, coord_size: int = 48) -> bytes:
    """
    COSE ECDSA signature is raw r||s (fixed width). Convert to DER for cryptography.
    coord_size = 48 for P-384 (r and s are 48 bytes each).
    """
    if len(sig) != 2 * coord_size:
        raise ValueError(f"Unexpected COSE signature length: {len(sig)} (want {2*coord_size})")
    r = int.from_bytes(sig[:coord_size], "big")
    s = int.from_bytes(sig[coord_size:], "big")
    return asn1_utils.encode_dss_signature(r, s)

@lru_cache(maxsize=256)
def _pubkey_from_leaf_cert_der(cert_der: bytes) -> ec.EllipticCurvePublicKey:
    leaf = x509.load_der_x509_certificate(cert_der)
    pub = leaf.public_key()
    if not isinstance(pub, ec.EllipticCurvePublicKey) or getattr(pub.curve, "name", None) != "secp384r1":
        raise ValueError("Unexpected signing key type/curve (expect P-384)")
    return pub

@lru_cache(maxsize=4096)
def _der_sig384_cached(sig: bytes) -> bytes:
    return _cose_ecdsa_sig_to_der(sig, 48)


# ---------------------------------------------------------------------------
# Chain validation (leaf -> intermediates -> pinned root)
# ---------------------------------------------------------------------------

def validate_attestation_chain_to_root(
    attestation: bytes,
    pinned_root_spki_sha256: bytes,
    at_time: Optional[dt.datetime] = None
) -> bool:
    """
    Validate the AWS Nitro Enclaves attestation certificate chain to a pinned root.

    Args:
      attestation: Raw bytes of the attestation document (CBOR COSE_Sign1).
      pinned_root_spki_sha256: SHA-256 of the trusted root's SPKI (bytes).
      at_time: Time to evaluate cert validity (defaults to now, UTC).

    Returns:
      True if the chain is valid and terminates at the pinned root; False otherwise.
    """
    try:
        # Decode COSE_Sign1 (AWS returns an untagged CBOR array)
        obj = cbor2.loads(attestation)
        if hasattr(obj, "tag"):
            obj = obj.value
        # COSE_Sign1 array: [protected bstr, unprotected map, payload bstr, signature bstr]
        _, _, payload_bstr, _ = obj

        # Extract payload -> { certificate, cabundle, ... }
        payload = cbor2.loads(payload_bstr)
        leaf_der = payload.get("certificate")
        bundle_ders = payload.get("cabundle") or []
        if not leaf_der or not isinstance(bundle_ders, list):
            return False

        leaf = x509.load_der_x509_certificate(leaf_der)
        pool: List[x509.Certificate] = [x509.load_der_x509_certificate(b) for b in bundle_ders]

        # Time validity check for all certificates
        now = at_time.astimezone(dt.timezone.utc) if at_time else dt.datetime.now(dt.timezone.utc)
        for cert in [leaf] + pool:
            nbf, naf = _cert_validity_window_utc(cert)
            if not (nbf <= now <= naf):
                return False

        # Build path leaf -> ... -> root by issuer DN matching + signature check
        chain: List[x509.Certificate] = [leaf]
        remaining = pool[:]
        visited = set()

        while True:
            current = chain[-1]

            # If current is self-signed, stop
            if current.subject == current.issuer:
                if not _verify_signed_by(current, current):
                    return False
                root = current
                break

            # Find an issuer in the remaining pool
            next_idx = -1
            for i, cand in enumerate(remaining):
                if cand.subject == current.issuer and _verify_signed_by(current, cand):
                    next_idx = i
                    break

            if next_idx == -1:
                # Could not find issuer; invalid/incomplete chain
                return False

            issuer = remaining.pop(next_idx)

            # Detect loops (paranoia)
            fp = issuer.fingerprint(hashes.SHA256())
            if fp in visited:
                return False
            visited.add(fp)

            chain.append(issuer)

        # Pin the root by SPKI hash
        if _spki_sha256(root) != pinned_root_spki_sha256:
            return False

        return True

    except Exception:
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Human-readable dump of the attestation payload
# ---------------------------------------------------------------------------

def attestation_to_json(attestation_doc_bytes: bytes) -> str:
    try:
        obj = cbor2.loads(attestation_doc_bytes)
        if hasattr(obj, "tag"):
            obj = obj.value
        # COSE_Sign1: [protected, unprotected, payload, signature]
        _, _, payload_bstr, _ = obj

        payload = cbor2.loads(payload_bstr)
        readable_payload = {}

        for key, value in payload.items():
            if key == "pcrs" and isinstance(value, dict):
                readable_payload[key] = {k: bytes(v).hex() for k, v in value.items()}

            elif key == "certificate" and isinstance(value, (bytes, bytearray)):
                cert = x509.load_der_x509_certificate(value)
                # Try *_utc first for newer cryptography; fallback otherwise.
                try:
                    not_before = cert.not_valid_before_utc.isoformat()
                    not_after = cert.not_valid_after_utc.isoformat()
                except AttributeError:
                    not_before = cert.not_valid_before.replace(tzinfo=None).isoformat()
                    not_after = cert.not_valid_after.replace(tzinfo=None).isoformat()

                readable_payload["certificate_details"] = {
                    "subject": cert.subject.rfc4514_string(),
                    "issuer": cert.issuer.rfc4514_string(),
                    "serial_number": cert.serial_number,
                    "valid_from_utc": not_before,
                    "valid_to_utc": not_after,
                }

            elif key == "cabundle" and isinstance(value, list):
                readable_payload[key] = [bytes(cert_bytes).hex() for cert_bytes in value]

            elif isinstance(value, (bytes, bytearray)):
                try:
                    readable_payload[key] = bytes(value).decode("utf-8")
                except UnicodeDecodeError:
                    readable_payload[key] = bytes(value).hex()

            elif isinstance(value, dt.datetime):
                readable_payload[key] = value.isoformat()

            else:
                readable_payload[key] = value

        return json.dumps(readable_payload, indent=4)

    except Exception as e:
        traceback.print_exc()
        return json.dumps({"error": f"Failed to parse attestation document: {e}"}, indent=4)


# ---------------------------------------------------------------------------
# Full validation: COSE signature + chain + optional bindings
# ---------------------------------------------------------------------------

def print_time(start: float, label: str = "Operation"):
    elapsed = (time.perf_counter() - start) * 1000
    print(f"✅ {label} succeeded in {elapsed:.2f} milliseconds.")

def validate(
    attestation: bytes,
    expected_user_data: Optional[bytes] = None,
    expected_bound_pubkey: Optional[bytes] = None,
    verify_chain: bool = False,   # set True if you want chain validation too
) -> bool:
    """
    Fast path: manual COSE Sig_structure + ES384 verify via cryptography/OpenSSL.
    Enforces alg=ES384, checks bound public_key and user_data, and can optionally
    validate the cert chain pinned to AWS Nitro root.
    """
    start = time.perf_counter()
    try:
        # 1) Decode COSE_Sign1 (AWS returns an untagged CBOR array)
        t1 = time.perf_counter()
        obj = cbor2.loads(attestation)
        if hasattr(obj, "tag"):
            obj = obj.value
        # COSE_Sign1 array: [protected bstr, unprotected map, payload bstr, signature bstr]
        phdr_bstr, _, payload_bstr, signature = obj
        print_time(t1, "COSE message decoded")

        # 2) Protected header: fast path equality; fallback to decode for alg check
        t2 = time.perf_counter()
        if phdr_bstr != _COSE_ES384_PROTECTED:
            prot = cbor2.loads(phdr_bstr) if phdr_bstr else {}
            if prot.get(1) != -35:  # 1 == "alg", -35 == ES384
                return False
        print_time(t2, "Protected header checked")

        # 3) Extract payload and signer key (leaf P-384)
        t3 = time.perf_counter()
        payload = cbor2.loads(payload_bstr)
        cert_der = payload.get("certificate")
        if not cert_der:
            return False
        pub = _pubkey_from_leaf_cert_der(cert_der)  # cached by DER
        print_time(t3, "Certificate & public key extracted")

        # 4) Verify COSE signature (manual Sig_structure, hashlib prehash, cached DER conversion)
        t4 = time.perf_counter()
        sig_structure = _make_sig_structure(phdr_bstr, payload_bstr)
        digest = hashlib.sha384(sig_structure).digest()
        der_sig = _der_sig384_cached(signature)
        pub.verify(der_sig, digest, ec.ECDSA(utils.Prehashed(hashes.SHA384())))
        print_time(t4, "Signature verified")

        # 5) Optional bindings (strict byte-for-byte)
        t5 = time.perf_counter()
        if expected_bound_pubkey is not None and payload.get("public_key") != expected_bound_pubkey:
            return False
        print_time(t5, "Public key binding verified")

        t6 = time.perf_counter()
        if expected_user_data is not None and payload.get("user_data") != expected_user_data:
            return False
        print_time(t6, "User data binding verified")

        # 6) Optional: chain validation to pinned root (compute digest lazily)
        if verify_chain:
            t7 = time.perf_counter()
            pinned = to_pinned_root_spki_sha256(config.AWS_NITRO_ROOT_CERT_PEM)
            if not validate_attestation_chain_to_root(attestation, pinned):
                return False
            print_time(t7, "Cert chain verified")

        elapsed = (time.perf_counter() - start) * 1000
        print(f"✅ Full Validation succeeded in {elapsed:.2f} milliseconds.")
        return True

    except Exception:
        traceback.print_exc()
        return False
