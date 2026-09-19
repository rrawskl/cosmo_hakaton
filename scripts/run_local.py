"""Start the installed project on Windows, Linux or macOS; Ctrl+C stops both servers."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def frontend_environment(environ):
    private = {
        "NASA_API_KEY",
        "SPACETRACK_USERNAME",
        "SPACETRACK_PASSWORD",
        "ADMIN_TOKEN",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
    }
    return {key: value for key, value in environ.items() if key.upper() not in private}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", action="store_true", help="Build frontend before starting"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    from dotenv import load_dotenv

    load_dotenv(root / ".env")
    frontend_env = frontend_environment(os.environ)
    node = shutil.which("node")
    cli = root / "frontend/node_modules/next/dist/bin/next"
    if not node or not cli.is_file():
        raise SystemExit(
            "Install Node.js and run pnpm install --frozen-lockfile in frontend first."
        )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    if args.build or not (root / "frontend/.next/BUILD_ID").is_file():
        subprocess.run(
            [node, str(cli), "build"],
            cwd=root / "frontend",
            check=True,
            env=frontend_env,
        )
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ]
            )
        )
        children.append(
            subprocess.Popen(
                [node, str(cli), "start", "--hostname", "127.0.0.1"],
                cwd=root / "frontend",
                env=frontend_env,
            )
        )
        print(
            "Orbital Risk: http://127.0.0.1:3000 — Ctrl+C stops both servers",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise SystemExit(
            "A server stopped. Check the logs above (ports 3000/8000 must be free)."
        )
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    child.terminate()
                child.wait(timeout=15)


if __name__ == "__main__":
    main()
