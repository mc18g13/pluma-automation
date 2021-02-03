from fastapi import FastAPI
from ..router import Router


class RootRouter(Router):
    def add_routes(self, app: FastAPI) -> FastAPI:
        @app.get('/')
        def _():
            return "Hello from Pluma!"

        return app