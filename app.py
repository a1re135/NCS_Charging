"""Run in VS Code: python app.py. Open http://127.0.0.1:5000."""

import os

from ncs import create_app


app = create_app()


if __name__ == "__main__":
    from waitress import serve

    port = int(
        os.environ.get("PORT")
        or os.environ.get(
            "NCS_PORT",
            "5000",
        )
    )

    threads = int(
        os.environ.get(
            "NCS_THREADS",
            "64",
        )
    )

    print(
        f"\nNCS Charging: "
        f"http://127.0.0.1:{port}\n"
        f"Waitress threads: {threads}\n"
        f"Press Ctrl+C to stop.\n",
        flush=True,
    )

    serve(
        app,
        host="0.0.0.0",
        port=port,
        threads=threads,
    )