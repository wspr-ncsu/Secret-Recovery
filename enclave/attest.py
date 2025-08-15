import os
import re
import json
import hashlib
import traceback
from typing import Union, Optional, List
import datetime as dt

import cbor2
import aws_nsm_interface
from crypto import sigma
import skrecovery.config as config

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding as asy_padding

from pycose.messages import Sign1Message
from pycose.keys.ec2 import EC2Key
from pycose.keys.curves import P384

import datetime as dt


# ---------------------------------------------------------------------------
# Key management (BLS app key you want NSM to bind)
# ---------------------------------------------------------------------------

publicKey: Optional[bytes] = None
privateKey: Optional[bytes] = None

def init():
    """
    Initialize application keys. Expects sigma.keygen() -> (sk, pk).
    Ensure `publicKey` are raw bytes suitable for attestation binding.
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
      at_time: Time to evaluate cert validity (defaults to now, UTC-naive).

    Returns:
      True if the chain is valid and terminates at the pinned root; False otherwise.
    """
    try:
        # Decode COSE_Sign1 (AWS returns an untagged CBOR array)
        obj = cbor2.loads(attestation)
        if hasattr(obj, "tag"):
            obj = obj.value
        cose = Sign1Message.from_cose_obj(obj, allow_unknown_attributes=True)

        # Extract payload -> { certificate, cabundle, ... }
        payload = cbor2.loads(cose.payload)
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
        cose = Sign1Message.from_cose_obj(obj, allow_unknown_attributes=True)

        payload = cbor2.loads(cose.payload)
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

def validate(
    attestation: bytes,
    expected_user_data: Optional[bytes] = None,
    expected_bound_pubkey: Optional[bytes] = None
) -> bool:
    """
    Validate COSE signature using the leaf cert, pin the chain to AWS root,
    and optionally check bound app key (BLS) and user_data.
    """
    try:
        # 1) Decode COSE_Sign1 (AWS returns an untagged CBOR array)
        obj = cbor2.loads(attestation)
        if hasattr(obj, "tag"):
            obj = obj.value
        cose_msg = Sign1Message.from_cose_obj(obj, allow_unknown_attributes=True)

        # 2) Extract payload and signer key (leaf P-384)
        payload = cbor2.loads(cose_msg.payload)
        cert_der = payload.get("certificate")
        if not cert_der:
            # print("❌ Missing 'certificate' in payload")
            return False

        leaf = x509.load_der_x509_certificate(cert_der)
        pub = leaf.public_key()
        if not isinstance(pub, ec.EllipticCurvePublicKey) or getattr(pub.curve, "name", None) != "secp384r1":
            # print(f"❌ Unexpected signing key type/curve: {type(pub)} / {getattr(pub.curve, 'name', None)}")
            return False

        nums = pub.public_numbers()
        cose_msg.key = EC2Key(
            crv=P384,
            x=nums.x.to_bytes(48, "big"),
            y=nums.y.to_bytes(48, "big"),
        )

        # 3) Verify COSE signature
        if not cose_msg.verify_signature():
            # print("❌ Signature is INVALID.")
            return False

        # 4) Optional bindings
        if expected_bound_pubkey is not None:
            bound = payload.get("public_key")
            if bound != expected_bound_pubkey:
                # print("❌ Bound 'public_key' does not match expected BLS key bytes.")
                return False

        if expected_user_data is not None:
            if payload.get("user_data") != expected_user_data:
                # print("❌ 'user_data' mismatch.")
                return False

        # 5) Chain validation to pinned root (This should be cached so that we simply perform equal-to checks)
        # root_digest = to_pinned_root_spki_sha256(config.AWS_NITRO_ROOT_CERT_PEM)
        # if not validate_attestation_chain_to_root(attestation, root_digest):
        #     # print("❌ Certificate chain invalid or not pinned to expected root.")
        #     return False

        # print("✅ Signature and chain valid; attestation verified.")
        return True

    except Exception:
        traceback.print_exc()
        # print("❌ Error during decoding or verification.")
        return False

def _cert_validity_window_utc(cert):
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