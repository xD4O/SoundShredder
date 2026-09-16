"""Stop the standalone server gracefully if its owning manager exits or crashes."""
import sys
import threading

import uvicorn

from desktop.lifetime import wait_for_owner


def main():
    server = uvicorn.Server(uvicorn.Config("soundshredder.server:app", host="127.0.0.1", port=int(sys.argv[1])))

    def owner_closed():
        wait_for_owner()
        server.should_exit = True

    threading.Thread(target=owner_closed, daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
