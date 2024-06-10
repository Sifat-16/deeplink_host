import os
from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

