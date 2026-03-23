import ast
import re
import logging
from typing import List

LOGGER = logging.getLogger(__name__)

_FUNCTION_PATTERNS = [
    re.compile(r'^(?:async\s+)?def\s+\w+', re.MULTILINE),
    re.compile(r'^class\s+\w+', re.MULTILINE),
    re.compile(r'^(?:export\s+)?(?:async\s+)?function\s+\w+', re.MULTILINE),
    re.compile(r'^(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(', re.MULTILINE),
    re.compile(r'^(?:pub\s+)?fn\s+\w+', re.MULTILINE),
    re.compile(r'^func\s+\w+', re.MULTILINE),
    re.compile(r'^(?:pub\s+)?(?:func|type|struct)\s+\w+', re.MULTILINE),
]


def split_code_at_boundaries(code: str, language: str = "", max_tokens: int = 256, token_counter=None) -> List[str]:
    if not code.strip():
        return []

    if token_counter and token_counter(code) <= max_tokens:
        return [code]

    if language.lower() in ('python', 'py', ''):
        result = _split_python_ast(code, max_tokens, token_counter)
        if result:
            return result

    result = _split_at_declarations(code, max_tokens, token_counter)
    if result and len(result) > 1:
        return result

    return _split_at_blank_lines(code, max_tokens, token_counter)


def _split_python_ast(code: str, max_tokens: int, token_counter) -> List[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    if not tree.body:
        return []

    lines = code.split('\n')
    boundaries = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            boundaries.append(node.lineno - 1)

    if not boundaries:
        return []

    chunks = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        chunk_text = '\n'.join(lines[start:end]).rstrip()
        if chunk_text.strip():
            chunks.append(chunk_text)

    if boundaries[0] > 0:
        preamble = '\n'.join(lines[:boundaries[0]]).rstrip()
        if preamble.strip():
            chunks.insert(0, preamble)

    if token_counter:
        chunks = _resplit_oversized(chunks, max_tokens, token_counter)

    return chunks if len(chunks) > 1 else []


def _split_at_declarations(code: str, max_tokens: int, token_counter) -> List[str]:
    lines = code.split('\n')
    split_points = [0]

    for i, line in enumerate(lines):
        if i == 0:
            continue
        stripped = line.rstrip()
        if not stripped:
            continue
        for pattern in _FUNCTION_PATTERNS:
            if pattern.match(stripped):
                if i > 0 and not lines[i - 1].strip():
                    split_points.append(i)
                elif i > 0:
                    split_points.append(i)
                break

    if len(split_points) <= 1:
        return []

    chunks = []
    for i, start in enumerate(split_points):
        end = split_points[i + 1] if i + 1 < len(split_points) else len(lines)
        chunk_text = '\n'.join(lines[start:end]).rstrip()
        if chunk_text.strip():
            chunks.append(chunk_text)

    if token_counter:
        chunks = _resplit_oversized(chunks, max_tokens, token_counter)

    return chunks


def _split_at_blank_lines(code: str, max_tokens: int, token_counter) -> List[str]:
    parts = re.split(r'\n\n+', code)
    parts = [p for p in parts if p.strip()]

    if not parts:
        return [code]

    if not token_counter:
        return parts

    chunks = []
    current_parts = []

    for part in parts:
        if current_parts:
            candidate = '\n\n'.join(current_parts + [part])
            if token_counter(candidate) > max_tokens:
                chunks.append('\n\n'.join(current_parts))
                current_parts = [part]
                continue

        current_parts.append(part)

    if current_parts:
        chunks.append('\n\n'.join(current_parts))

    return chunks if chunks else [code]


def _resplit_oversized(chunks: List[str], max_tokens: int, token_counter) -> List[str]:
    result = []
    for chunk in chunks:
        if token_counter(chunk) <= max_tokens:
            result.append(chunk)
        else:
            sub = _split_at_blank_lines(chunk, max_tokens, token_counter)
            result.extend(sub)
    return result
