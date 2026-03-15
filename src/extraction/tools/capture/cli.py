import argparse
from pathlib import Path
import sys

from .app import CaptureApp
from .core.session import CaptureSession


def main():
    parser = argparse.ArgumentParser(
        description="Interactive chunk capture tool - select and capture text regions"
    )

    parser.add_argument(
        "document",
        type=Path,
        help="Path to EPUB, extraction JSON, JSONL, or text file",
    )

    parser.add_argument(
        "--session-file",
        type=Path,
        help="Path to session file (default: .capture_sessions/<filename>.json)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume existing session",
    )

    parser.add_argument(
        "--grpc-target",
        default="localhost:50051",
        help="gRPC server address for token counting (default: localhost:50051)",
    )

    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Export captured chunks without opening TUI",
    )

    parser.add_argument(
        "--export-format",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Export format: jsonl (flat) or json (extraction-compatible)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for export",
    )

    args = parser.parse_args()

    if not args.document.exists():
        print(f"Error: File not found: {args.document}")
        sys.exit(1)

    if args.export_only:
        _export(args)
        return

    print(f"Loading {args.document.name}...")
    app = CaptureApp(
        document_path=args.document,
        session_file=args.session_file,
        resume=args.resume,
        grpc_target=args.grpc_target,
    )
    app.load_document()
    app.run()


def _export(args):
    session_file = args.session_file
    if session_file is None:
        session_name = args.document.stem
        session_file = Path(f".capture_sessions/{session_name}.json")

    if not session_file.exists():
        print(f"Error: Session file not found: {session_file}")
        sys.exit(1)

    session = CaptureSession(
        document_path=args.document,
        session_file=session_file,
    )

    output = args.output
    if output is None:
        suffix = ".captured.jsonl" if args.export_format == "jsonl" else ".captured.json"
        output = args.document.with_suffix(suffix)

    if args.export_format == "jsonl":
        count = session.export_jsonl(output)
    else:
        count = session.export_extraction_json(output)

    print(f"Exported {count} chunks to {output}")


if __name__ == "__main__":
    main()
