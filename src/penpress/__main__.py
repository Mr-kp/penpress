"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from penpress import __version__
from penpress.api.server import run_server
from penpress.plan.render import execute_document_pipeline, execute_render_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the PenPress command line parser."""
    parser = argparse.ArgumentParser(
        prog="penpress",
        description="PenPress: Plot assignments in authentic handwriting on Marlin 3D plotters.",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"penpress {__version__}",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # render subcommand (unified PDF, Markdown+LaTeX, text)
    render_doc_parser = subparsers.add_parser(
        "render",
        help="Compile PDF, Markdown+LaTeX, or text assignment to natural handwriting G-code, PNG, and SVG.",
    )
    render_doc_parser.add_argument(
        "file",
        type=Path,
        help="Path to input assignment file (.pdf, .md, .txt).",
    )
    render_doc_parser.add_argument(
        "--paper",
        default="A5",
        choices=["A5", "A4"],
        help="Target paper size (default: A5).",
    )
    render_doc_parser.add_argument(
        "--profile",
        default="ender3pro",
        help="Machine profile name (default: ender3pro) or path to .toml profile.",
    )
    render_doc_parser.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        default=Path("out"),
        help="Output directory for generated G-code, PNG, SVG, and summary artifacts (default: out/).",
    )
    render_doc_parser.add_argument(
        "--optimize",
        dest="optimize",
        action="store_true",
        default=True,
        help="Optimize toolpaths using TSP 2-opt and collinear segment merging (default: True).",
    )
    render_doc_parser.add_argument(
        "--no-optimize",
        dest="optimize",
        action="store_false",
        help="Disable TSP 2-opt toolpath optimization.",
    )

    # render-text subcommand
    render_parser = subparsers.add_parser(
        "render-text",
        help="Compile text file to G-code and verify execution with the virtual Marlin simulator.",
    )
    render_parser.add_argument(
        "file",
        type=Path,
        help="Path to input text file (.txt).",
    )
    render_parser.add_argument(
        "--profile",
        default="ender3pro",
        help="Machine profile name (default: ender3pro) or path to .toml profile.",
    )
    render_parser.add_argument(
        "--out",
        dest="out_dir",
        type=Path,
        default=Path("out"),
        help="Output directory for generated G-code, PNG, and SVG artifacts (default: out/).",
    )
    render_parser.add_argument(
        "--font-size",
        type=float,
        default=3.5,
        help="Font cap height in millimetres (default: 3.5).",
    )
    render_parser.add_argument(
        "--line-height",
        type=float,
        default=8.5,
        help="Line spacing in millimetres (default: 8.5).",
    )
    render_parser.add_argument(
        "--paginate",
        action="store_true",
        help="Allow overflowing text to paginate into multiple sheets.",
    )
    render_parser.add_argument(
        "--ocr-mode",
        action="store_true",
        help="Render simulator PNG in high-contrast black-on-white mode optimized for OCR.",
    )

    # serve subcommand
    serve_parser = subparsers.add_parser(
        "serve",
        help="Launch the PenPress Studio web interface and REST API daemon.",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1).",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080).",
    )

    return parser


def _handle_serve(args: argparse.Namespace) -> int:
    try:
        run_server(host=args.host, port=args.port)
        return 0
    except Exception as exc:
        print(f"Error starting server: {exc}", file=sys.stderr)
        return 1


def _handle_render(args: argparse.Namespace) -> int:
    try:
        profile_arg = str(args.profile)
        profile_path = Path(profile_arg) if profile_arg.endswith(".toml") else None
        profile_name = profile_arg if not profile_arg.endswith(".toml") else "custom"

        execute_document_pipeline(
            file_path=args.file,
            output_dir=args.out_dir,
            paper=args.paper,
            profile_path=profile_path,
            profile_name=profile_name,
            optimize=args.optimize,
            out_stream=sys.stdout,
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _handle_render_text(args: argparse.Namespace) -> int:
    try:
        profile_arg = str(args.profile)
        profile_path = Path(profile_arg) if profile_arg.endswith(".toml") else None
        profile_name = profile_arg if not profile_arg.endswith(".toml") else "custom"

        execute_render_pipeline(
            text_file=args.file,
            output_dir=args.out_dir,
            profile_path=profile_path,
            profile_name=profile_name,
            font_size_mm=args.font_size,
            line_height_mm=args.line_height,
            paginate=args.paginate,
            ocr_mode=args.ocr_mode,
            out_stream=sys.stdout,
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args_list = sys.argv[1:] if argv is None else argv

    if args_list and args_list[0] in {"--version", "-V"}:
        print(f"penpress {__version__}")
        return 0

    parser = build_parser()
    if not args_list:
        parser.print_help(sys.stderr)
        return 2

    args = parser.parse_args(args_list)

    if args.subcommand == "render":
        return _handle_render(args)
    if args.subcommand == "serve":
        return _handle_serve(args)
    if args.subcommand == "render-text":
        return _handle_render_text(args)

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
