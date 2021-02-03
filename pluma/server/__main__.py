import uvicorn
from pluma.server.app import create_app


def server_main():
    app = create_app()

    # Setup any server arguments here

    uvicorn.run(app)


if __name__ == '__main__':
    server_main()