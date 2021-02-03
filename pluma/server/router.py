from fastapi import FastAPI
from abc import ABC, abstractmethod


class Router(ABC):
    @abstractmethod
    def add_routes(self, app: FastAPI) -> FastAPI:
        '''Register routes on the app and pass it on to the next router'''