from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from cryptography.fernet import Fernet
import base64
import json
import requests
import os
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

SECRET_KEY = os.environ.get("SECRET_KEY", "CHANGE_THIS_TO_RANDOM_32_CHARS_KEY")
if len(SECRET_KEY) < 32:
    SECRET_KEY = SECRET_KEY.ljust(32, "0")
cipher = Fernet(base64.urlsafe_b64encode(SECRET_KEY.encode()[:32].ljust(32, b"=")))

@app.get("/")
def health():
    return {"status": "alive", "service": "oblivious-relay"}

@app.post("/relay")
async def relay(request: Request):
    try:
        data = await request.json()
        
        if "encrypted" not in data:
            raise HTTPException(status_code=400, detail="Missing encrypted field")
        
        decrypted_json = cipher.decrypt(data["encrypted"].encode())
        decrypted = json.loads(decrypted_json)
        
        if "url" not in decrypted:
            raise HTTPException(status_code=400, detail="Missing url in decrypted data")
        
        method = decrypted.get("method", "GET")
        headers = decrypted.get("headers", {})
        body = decrypted.get("body")
        timeout = decrypted.get("timeout", 30)
        
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        logging.info(f"Relaying {method} request to: {decrypted['url']}")
        
        response = requests.request(
            method=method,
            url=decrypted["url"],
            headers=headers,
            data=body if isinstance(body, str) else json.dumps(body) if body else None,
            timeout=timeout,
            verify=True
        )
        
        result = {
            "status": response.status_code,
            "headers": dict(response.headers),
            "body": base64.b64encode(response.content).decode()
        }
        
        encrypted_response = cipher.encrypt(json.dumps(result).encode())
        
        return JSONResponse(content={"encrypted": encrypted_response.decode()})
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        error_response = cipher.encrypt(json.dumps({
            "status": 500,
            "error": str(e),
            "body": base64.b64encode(f"Relay error: {str(e)}".encode()).decode()
        }).encode())
        return JSONResponse(content={"encrypted": error_response.decode()}, status_code=200)