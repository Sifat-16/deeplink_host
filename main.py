from typing import Union
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
)


app.mount("/.well-known", StaticFiles(directory="static/.well-known"), name="well-known")

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/community")
def read_root():
    return {"Hello": "Came to community, need to redirect to app"}

