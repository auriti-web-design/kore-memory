"""
Kore — CLI entry point
Usage: kore [--host HOST] [--port PORT] [--reload]
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kore",
        description="Kore memory server — start the API.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    parser.add_argument("--log-level", default="warning", choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not found. Run: pip install kore-memory", file=sys.stderr)
        sys.exit(1)

    uvicorn.run(
        "kore_memory.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
