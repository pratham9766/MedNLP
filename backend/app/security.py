import base64, hashlib, hmac, json, secrets, time
from app.core.config import settings

def hash_password(password:str)->str:
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,310_000)
    return base64.urlsafe_b64encode(salt).decode()+"."+base64.urlsafe_b64encode(digest).decode()

def verify_password(password:str,stored:str)->bool:
    try:
        salt,expected=stored.split("."); actual=hashlib.pbkdf2_hmac("sha256",password.encode(),base64.urlsafe_b64decode(salt),310_000)
        return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode(),expected)
    except Exception:return False

def issue_token(user_id:int)->str:
    payload=base64.urlsafe_b64encode(json.dumps({"sub":user_id,"exp":int(time.time())+86400}).encode()).decode().rstrip("=")
    signature=base64.urlsafe_b64encode(hmac.new(settings.secret_key.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip("=")
    return payload+"."+signature

def token_user(token:str)->int|None:
    try:
        payload,sig=token.split("."); expected=base64.urlsafe_b64encode(hmac.new(settings.secret_key.encode(),payload.encode(),hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(sig,expected): return None
        data=json.loads(base64.urlsafe_b64decode(payload+"=="));
        return int(data["sub"]) if data["exp"]>time.time() else None
    except Exception:return None
