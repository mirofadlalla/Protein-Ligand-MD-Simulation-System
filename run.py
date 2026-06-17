#!/usr/bin/env python3
"""
run.py — CLI entry point for the MD Simulation server.

Usage
-----
    python run.py                        # start with defaults
    python run.py --host 0.0.0.0 --port 5005 --debug

Environment variables (override CLI defaults):
    FLASK_HOST       default: 0.0.0.0
    FLASK_PORT       default: 5005
    FLASK_DEBUG      default: false
    MD_DATA_DIR      default: ./data
    OPENMM_PLATFORM  default: AUTO   (CUDA | OpenCL | CPU)
    LOG_LEVEL        default: INFO
"""

import argparse
import sys

from app.config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from app.main import create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Protein-Ligand MD Simulation API Server"
    )
    parser.add_argument(
        "--host", default=FLASK_HOST,
        help=f"Bind address (default: {FLASK_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=FLASK_PORT,
        help=f"Port (default: {FLASK_PORT})"
    )
    parser.add_argument(
        "--debug", action="store_true", default=FLASK_DEBUG,
        help="Enable Flask debug mode"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app  = create_app()

    print(f"\n  MD Simulation API Server")
    print(f"  ─────────────────────────────────")
    print(f"  Host  : {args.host}")
    print(f"  Port  : {args.port}")
    print(f"  Debug : {args.debug}")
    print(f"  Docs  : http://{args.host}:{args.port}/health\n")

    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    main()
