"""
LLM-powered question generation for chunks.

Post-processing tool that reads extraction JSON output and enriches
chunks with hypothetical questions for HyDE-style retrieval.

Supports template-based (no LLM) and LLM-powered modes.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

LOGGER = logging.getLogger(__name__)

_HEADING_NUM_RE = re.compile(r'^\d+(\.\d+)*\s+')


def _strip_heading_number(text: str) -> str:
    return _HEADING_NUM_RE.sub('', text)


SYSTEM_PROMPT = """Generate 3-5 concise questions that a user might ask which this text chunk would answer.
Return ONLY the questions, one per line. No numbering, no explanations.
Questions should be natural language queries a person would type into a search bar."""


def generate_questions_template(chunk: Dict[str, Any], doc_title: str = "") -> List[str]:
    questions = []
    hierarchy = chunk.get('hierarchy', {})
    levels = [hierarchy.get(f'level_{i}', '') for i in range(1, 7)]
    levels = [_strip_heading_number(l) for l in levels if l]
    content_type = chunk.get('content_type', 'prose')

    if content_type == 'code':
        if levels:
            questions.append(f"How is {levels[-1]} implemented?")
        text = chunk.get('text', '')
        first_line = text.split('\n')[0].strip() if text else ""
        if first_line.startswith('def ') or first_line.startswith('async def '):
            func_name = first_line.split('(')[0].replace('def ', '').replace('async ', '').strip()
            if func_name:
                questions.append(f"What does {func_name} do?")
                questions.append(f"How to use {func_name}?")
        elif first_line.startswith('class '):
            class_name = first_line.split('(')[0].split(':')[0].replace('class ', '').strip()
            if class_name:
                questions.append(f"What is {class_name}?")
                questions.append(f"How to use {class_name}?")
    else:
        if len(levels) >= 2:
            questions.append(f"What is {levels[-1]}?")
            questions.append(f"What does {levels[-1]} cover in {levels[-2]}?")
        elif len(levels) == 1:
            questions.append(f"What is {levels[0]} about?")

        if doc_title and levels:
            questions.append(f"What does {doc_title} say about {levels[-1]}?")

        for ref in chunk.get('scripture_references', [])[:2]:
            questions.append(f"What does {ref} say?")

    return questions


def generate_questions_llm(
    chunk: Dict[str, Any],
    client,
    model: str = "claude-sonnet-4-20250514",
) -> List[str]:
    text = chunk.get('text', '')
    heading = chunk.get('heading_path', '')
    content_type = chunk.get('content_type', 'prose')

    user_msg = f"Content type: {content_type}\n"
    if heading:
        user_msg += f"Section: {heading}\n"
    user_msg += f"\n---\n{text[:2000]}"

    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text
    questions = [q.strip() for q in raw.strip().split('\n') if q.strip()]
    return questions[:5]


def enrich_document(
    data: Dict[str, Any],
    mode: str = "template",
    client=None,
    model: str = "claude-sonnet-4-20250514",
) -> Dict[str, Any]:
    chunks = data.get('chunks', [])
    enriched = 0

    for chunk in chunks:
        if chunk.get('hypothetical_questions'):
            continue

        if mode == "llm" and client:
            try:
                questions = generate_questions_llm(chunk, client, model)
            except Exception as e:
                LOGGER.warning("LLM generation failed for chunk %s: %s", chunk.get('stable_id', '?'), e)
                questions = generate_questions_template(chunk)
        else:
            questions = generate_questions_template(chunk)

        if questions:
            chunk['hypothetical_questions'] = questions
            enriched += 1

    LOGGER.info("Generated questions for %d/%d chunks", enriched, len(chunks))
    return data


def main():
    ap = argparse.ArgumentParser(
        description="Generate hypothetical questions for chunks (HyDE-style retrieval enhancement)."
    )
    ap.add_argument("input", help="Path to extraction JSON file")
    ap.add_argument("-o", "--output", help="Output path (default: overwrite input)")
    ap.add_argument(
        "--mode",
        choices=["template", "llm"],
        default="template",
        help="Generation mode: template (free, no API) or llm (requires API key)",
    )
    ap.add_argument("--model", default="claude-sonnet-4-20250514", help="LLM model for --mode llm")
    ap.add_argument("-v", "--verbose", action="store_true")

    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        LOGGER.error("File not found: %s", input_path)
        return 1

    with open(input_path) as f:
        data = json.load(f)

    client = None
    if args.mode == "llm":
        try:
            import anthropic
            client = anthropic.Anthropic()
        except ImportError:
            LOGGER.error("anthropic package required for --mode llm: uv pip install anthropic")
            return 1
        except Exception as e:
            LOGGER.error("Failed to initialize Anthropic client: %s", e)
            return 1

    data = enrich_document(data, mode=args.mode, client=client, model=args.model)

    output_path = Path(args.output) if args.output else input_path
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote enriched output to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
