"""CLI entry point for annotation tool."""

import argparse
from pathlib import Path
import sys

from .app import AnnotationApp
from .core.chunk_loader import ChunkLoader
from .core.session import AnnotationSession
from .core.dataset_export import DatasetExporter


def export_only(
    chunks_file: Path,
    session_file: Path,
    output_path: Path,
    export_type: str,
) -> None:
    """Export annotations without opening TUI.

    Args:
        chunks_file: Path to chunks file
        session_file: Path to session file
        output_path: Output path
        export_type: Type of export (jsonl, split, issues, labels)
    """
    if not session_file.exists():
        print(f"Error: Session file not found: {session_file}")
        sys.exit(1)

    chunks = ChunkLoader.load(chunks_file)
    session = AnnotationSession(
        chunks=chunks,
        session_file=session_file,
    )

    annotations = {
        chunk_id: ann.to_dict()
        for chunk_id, ann in session.annotations.items()
    }

    if export_type == "jsonl":
        count = DatasetExporter.export_jsonl(
            chunks,
            annotations,
            output_path,
        )
        print(f"Exported {count} annotations to {output_path}")

    elif export_type == "split":
        output_dir = output_path.parent
        train_count, test_count = DatasetExporter.export_train_test_split(
            chunks,
            annotations,
            output_dir,
        )
        print(f"Exported {train_count} train, {test_count} test to {output_dir}/")

    elif export_type == "issues":
        output_dir = output_path.parent / "issues"
        counts = DatasetExporter.export_by_issues(
            chunks,
            annotations,
            output_dir,
        )
        total = sum(counts.values())
        print(f"Exported {total} chunks across {len(counts)} issues to {output_dir}/")

    elif export_type == "labels":
        output_dir = output_path.parent / "labels"
        counts = DatasetExporter.export_by_labels(
            chunks,
            annotations,
            output_dir,
        )
        print(f"Exported {counts.get(0, 0)} good, {counts.get(1, 0)} bad to {output_dir}/")

    elif export_type == "edited":
        count = DatasetExporter.export_edited_jsonl(
            chunks,
            annotations,
            session.edited_chunks,
            output_path,
        )
        print(f"Exported {count} chunks (with edits) to {output_path}")

    elif export_type == "audit":
        count = DatasetExporter.export_audit_jsonl(
            chunks,
            annotations,
            session.edited_chunks,
            output_path,
        )
        print(f"Exported {count} chunks with full audit trail to {output_path}")

    elif export_type == "diff":
        count = DatasetExporter.export_diff_report(
            chunks,
            session.edited_chunks,
            output_path,
        )
        print(f"Exported {count} edited chunks with diffs to {output_path}")


def stats_only(chunks_file: Path, session_file: Path) -> None:
    """Show statistics without opening TUI.

    Args:
        chunks_file: Path to chunks file
        session_file: Path to session file
    """
    if not session_file.exists():
        print(f"Error: Session file not found: {session_file}")
        sys.exit(1)

    chunks = ChunkLoader.load(chunks_file)
    session = AnnotationSession(
        chunks=chunks,
        session_file=session_file,
    )

    stats = session.stats

    print("\n=== Annotation Statistics ===")
    print(f"Total chunks: {stats.total_chunks}")
    print(f"Annotated: {stats.annotated_count}")
    print(f"Good: {stats.good_count}")
    print(f"Bad: {stats.bad_count}")
    print(f"Skipped: {stats.skipped_count}")

    progress = session.get_progress_percent()
    print(f"Progress: {progress:.1f}%")

    if stats.annotated_count > 0:
        good_rate = (stats.good_count / stats.annotated_count) * 100
        bad_rate = (stats.bad_count / stats.annotated_count) * 100
        print(f"Good rate: {good_rate:.1f}%")
        print(f"Bad rate: {bad_rate:.1f}%")

    if stats.issue_counts:
        print("\n=== Issue Distribution ===")
        sorted_issues = sorted(
            stats.issue_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for issue, count in sorted_issues:
            issue_display = issue.replace("_", " ").title()
            if issue.startswith("other:"):
                issue_display = issue.replace("other:", "Other: ", 1)
            print(f"{issue_display}: {count}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive chunk quality annotation tool"
    )

    parser.add_argument(
        "chunks_file",
        type=Path,
        help="Path to chunks JSON or JSONL file",
    )

    parser.add_argument(
        "--session-file",
        type=Path,
        help="Path to session file (default: .annotation_sessions/<filename>.json)",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume existing session",
    )

    parser.add_argument(
        "--annotator-id",
        default="default",
        help="Annotator identifier (default: default)",
    )

    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Export annotations without opening TUI",
    )

    parser.add_argument(
        "--export-type",
        choices=["jsonl", "split", "issues", "labels", "edited", "audit", "diff"],
        default="jsonl",
        help="Export type when using --export-only (edited=with edits, audit=full lineage, diff=markdown report)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("annotations.jsonl"),
        help="Output path for export (default: annotations.jsonl)",
    )

    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show statistics without opening TUI",
    )

    args = parser.parse_args()

    if not args.chunks_file.exists():
        print(f"Error: Chunks file not found: {args.chunks_file}")
        sys.exit(1)

    session_file = args.session_file
    if session_file is None:
        session_name = args.chunks_file.stem
        session_file = Path(f".annotation_sessions/{session_name}.json")

    if args.export_only:
        export_only(
            args.chunks_file,
            session_file,
            args.output,
            args.export_type,
        )
        return

    if args.stats_only:
        stats_only(args.chunks_file, session_file)
        return

    app = AnnotationApp(
        chunks_file=args.chunks_file,
        session_file=session_file,
        resume=args.resume,
        annotator_id=args.annotator_id,
    )

    app.run()


if __name__ == "__main__":
    main()
