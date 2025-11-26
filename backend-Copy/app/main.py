from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from .syscall_wrapper import call_custom_syscall

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/usage")
def get_usage(pid: int = Query(...)):
    return call_custom_syscall(pid)