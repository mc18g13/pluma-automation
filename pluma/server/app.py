from fastapi import FastAPI


# Uvicorn will use this function as a factory to create the ASGI app
def create_app() -> FastAPI:
    return FastAPI()