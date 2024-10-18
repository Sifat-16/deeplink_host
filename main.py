import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from urllib.parse import urlencode
from pydantic import BaseModel
from src.RtcTokenBuilder2 import *

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
)


# Define a Pydantic model for the request body
class TokenRequest(BaseModel):
    channel_name: str
    account: int


#app.mount("/.well-known", StaticFiles(directory="static/.well-known"), name="well-known")

@app.get("/")
def read_root():
    return {"Hello": "World"}


# Serve the assetlinks.json file directly without redirects
@app.get("/.well-known/assetlinks.json", response_class=FileResponse)
def read_assetlinks():
    json_path = os.path.join("static", ".well-known", "assetlinks.json")
    return FileResponse(path=json_path, media_type="application/json")


@app.get("/.well-known/apple-app-site-association", response_class=FileResponse)
def read_apple_site_association():
    json_path = os.path.join("static", ".well-known", "apple-app-site-association")
    return FileResponse(path=json_path, media_type="application/json")


@app.get("/community")
def read_root():
    return {"Hello": "Came to community, need to redirect to app"}


ZOOM_MEETING_CLIENT_ID = os.getenv('ZOOM_MEETING_CLIENT_ID', 'tR6vFXdLQiaw_F_I6_wqHw')
ZOOM_MEETING_CLIENT_SECRET = os.getenv('ZOOM_MEETING_CLIENT_SECRET', 'Xs83FKDgFE70jccBkHlDvRm58qQcp7z5')
ZOOM_MEETING_REDIRECT_URL = os.getenv('ZOOM_MEETING_REDIRECT_URL', 'http://localhost:8000/zoomtoken')
ZOOM_MEETING_AUTHORIZATION_CODE = os.getenv('ZOOM_MEETING_AUTHORIZATION_CODE', 'L096NfUcKiMh2GhnO8xTeS-VDZ8zMuyjA')
ZOOM_TOKEN_URL = os.getenv('ZOOM_TOKEN_URL', 'https://zoom.us/oauth/token')
ZOOM_REFRESH_TOKEN = os.getenv('ZOOM_REFRESH_TOKEN',
                               'eyJzdiI6IjAwMDAwMSIsImFsZyI6IkhTNTEyIiwidiI6IjIuMCIsImtpZCI6Ijg3Yjc0YzI5LTQyY2MtNDYyOC1iODNkLTExZDU0MDMxZmYxOCJ9.eyJ2ZXIiOjksImF1aWQiOiIyNWI4MDk5YjAxYmQ0ZjM4MTUwYmRhYjAyZTczMjg2NSIsImNvZGUiOiJMMDk2TmZVY0tpTWgyR2huTzh4VGVTLVZEWjh6TXV5akEiLCJpc3MiOiJ6bTpjaWQ6dFI2dkZYZExRaWF3X0ZfSTZfd3FIdyIsImdubyI6MCwidHlwZSI6MSwidGlkIjozLCJhdWQiOiJodHRwczovL29hdXRoLnpvb20udXMiLCJ1aWQiOiJGc2cwcXpRS1RBMjIxbG5takZqeUZBIiwibmJmIjoxNzE5NjU5NTgyLCJleHAiOjE3Mjc0MzU1ODIsImlhdCI6MTcxOTY1OTU4MiwiYWlkIjoiamVGTDRjUWVUS0t3V1RtZkd5NjJwdyJ9.mUQ16UlCBRPYlhxhBqGFMCrH2FSkKOvX-JnH4jsprURj7R7yepErjDyt3KWuMdrulbx7LsK_7feV3zPnxkH2nw')
ZOOM_BASE_API_URL = 'https://api.zoom.us/v2'

cached_token = None
cached_token_expiry = None


def request_zoom_token(authorization_code=ZOOM_MEETING_AUTHORIZATION_CODE):
    global cached_token, cached_token_expiry

    data = {
        'grant_type': 'authorization_code',
        'code': authorization_code,
        'redirect_uri': ZOOM_MEETING_REDIRECT_URL,
    }

    auth_str = f'{ZOOM_MEETING_CLIENT_ID}:{ZOOM_MEETING_CLIENT_SECRET}'
    print(auth_str)
    auth_base64 = base64.b64encode(auth_str.encode()).decode('utf-8')

    headers = {
        'Authorization': 'Basic ' + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.post(ZOOM_TOKEN_URL, data=urlencode(data), headers=headers)

    print(response.json())

    if response.status_code == 200:
        token_data = response.json()
        cached_token = token_data
        cached_token_expiry = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
        return token_data
    else:
        print('Error requesting zoom token:', response.json())
        return None


def refresh_zoom_token(refresh_token=None):
    global cached_token, cached_token_expiry

    token = refresh_token or (cached_token and cached_token.get('refresh_token'))
    if not token:
        raise HTTPException(status_code=400, detail="No refresh token found")

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': token,
    }

    auth_str = f'{ZOOM_MEETING_CLIENT_ID}:{ZOOM_MEETING_CLIENT_SECRET}'
    auth_base64 = base64.b64encode(auth_str.encode()).decode('utf-8')

    headers = {
        'Authorization': 'Basic ' + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.post(ZOOM_TOKEN_URL, data=urlencode(data), headers=headers)

    if response.status_code == 200:
        token_data = response.json()
        cached_token = token_data
        cached_token_expiry = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
        return token_data
    else:
        print('Error refreshing zoom token:', response.json())
        return None


def get_access_token():
    global cached_token, cached_token_expiry

    if cached_token and cached_token_expiry and cached_token_expiry > datetime.utcnow():
        return cached_token['access_token']

    new_token = request_zoom_token()
    if new_token:
        return new_token['access_token']
    return None


def zoom_api_request(url, method='GET', data=None):
    access_token = get_access_token()
    if not access_token:
        raise HTTPException(status_code=400, detail="Could not get access token")

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    if method == 'GET':
        response = requests.get(ZOOM_BASE_API_URL + url, headers=headers)
    elif method == 'POST':
        response = requests.post(ZOOM_BASE_API_URL + url, headers=headers, json=data)
    else:
        raise HTTPException(status_code=400, detail="Unsupported method")

    if response.status_code == 401:
        new_token = refresh_zoom_token()
        if new_token:
            headers['Authorization'] = f'Bearer {new_token["access_token"]}'
            if method == 'GET':
                response = requests.get(ZOOM_BASE_API_URL + url, headers=headers)
            elif method == 'POST':
                response = requests.post(ZOOM_BASE_API_URL + url, headers=headers, json=data)
        else:
            raise HTTPException(status_code=400, detail="Could not refresh token")

    return response.json()


@app.get("/zoomtoken")
async def zoom_token(request: Request):
    authorization_code = request.query_params.get('code')
    token_data = request_zoom_token(authorization_code)
    return JSONResponse(content=token_data)


@app.post("/refresh")
async def refresh_token(request: Request):
    request_data = await request.json()
    print(request_data)
    refresh_token = request_data.get('refresh_token')
    token_data = refresh_zoom_token(refresh_token)
    return JSONResponse(content=token_data)


@app.api_route("/zoom_api/{endpoint:path}", methods=["GET", "POST"])
async def zoom_api(request: Request, endpoint: str):
    method = request.method
    data = await request.json() if method == 'POST' else None
    response = zoom_api_request('/' + endpoint, method, data)
    return JSONResponse(content=response)


@app.api_route("/enigma-token/generate", methods=["POST"])
async def enigma_token_generate(request: Request, token_request: TokenRequest):
    # Need to set environment variable AGORA_APP_ID
    app_id = "a043b1dd233440b8a8435966f4a9dab3"
    # Need to set environment variable AGORA_APP_CERTIFICATE
    app_certificate = "86cebf0cf6314172b235295362a2807a"

    channel_name = token_request.channel_name
    account = token_request.account
    token_expiration_in_seconds = 36000
    privilege_expiration_in_seconds = 3600

    try:
        # Generate the token using Agora's RtcTokenBuilder
        token = RtcTokenBuilder.build_token_with_uid(
            app_id, app_certificate, channel_name, account, 1,
            token_expiration_in_seconds
        )
        # Return the generated token as a JSON response
        return JSONResponse(content={"token": token})

    except Exception as e:
        # Handle exceptions and return a 500 error response if token generation fails
        raise HTTPException(status_code=500, detail=f"Token generation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
