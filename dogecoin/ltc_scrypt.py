# Pure-Python stand-in for the ltc_scrypt extension that Dogecoin's qa framework imports for block hashes
# (scrypt with N=1024, r=1, p=1). Enough for qa/rpc-tests/pqsig-softfork.py; copy it into qa/rpc-tests/.
import hashlib


def getPoWHash(data):
    return hashlib.scrypt(bytes(data), salt=bytes(data), n=1024, r=1, p=1, dklen=32)
