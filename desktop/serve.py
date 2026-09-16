"""Stop the standalone server gracefully if its owning manager exits or crashes."""
import os
import sys
import threading

import uvicorn


def main():
    server = uvicorn.Server(uvicorn.Config("soundshredder.server:app", host="127.0.0.1", port=int(sys.argv[1])))

    def owner_closed():
        # Avoid holding Python's buffered-stdin lock while native libraries import.
        while os.read(sys.stdin.fileno(), 1):
            pass
        server.should_exit = True

    threading.Thread(target=owner_closed, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
