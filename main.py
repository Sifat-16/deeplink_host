import os
from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import jwt
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from urllib.parse import urlencode

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
)


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

    headers = {
        'Authorization': 'Basic ' + f'{ZOOM_MEETING_CLIENT_ID}:{ZOOM_MEETING_CLIENT_SECRET}'.encode('utf-8').decode(
            'base64'),
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.post(ZOOM_TOKEN_URL, data=urlencode(data), headers=headers)

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

    headers = {
        'Authorization': 'Basic ' + f'{ZOOM_MEETING_CLIENT_ID}:{ZOOM_MEETING_CLIENT_SECRET}'.encode('utf-8').decode(
            'base64'),
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
    refresh_token = request_data.get('refresh_token')
    token_data = refresh_zoom_token(refresh_token)
    return JSONResponse(content=token_data)


@app.api_route("/zoom_api/{endpoint:path}", methods=["GET", "POST"])
async def zoom_api(request: Request, endpoint: str):
    method = request.method
    data = await request.json() if method == 'POST' else None
    response = zoom_api_request('/' + endpoint, method, data)
    return JSONResponse(content=response)







