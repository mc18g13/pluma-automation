from pluma.server.routes.root import RootRouter
from fastapi import FastAPI


# Uvicorn will use this function as a factory to create the ASGI app
def create_app() -> FastAPI:
    app = FastAPI()

    # Add routes
    app = RootRouter().add_routes(app)

    return app
