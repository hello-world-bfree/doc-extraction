"""Code indentation inside <pre> survives EPUB extraction."""

from test_epub_nested_duplication import _raw_units

HIGHLIGHTED_PRE = (
    '<pre data-type="programlisting" data-code-language="python">'
    '<code class="k">def</code> <code class="nf">handle</code><code class="p">(</code>\n'
    '        <code class="n">event</code><code class="p">):</code>\n'
    '    <code class="k">with</code> <code class="n">uow</code><code class="p">:</code>\n'
    '        <code class="n">uow</code><code class="o">.</code><code class="n">commit</code><code class="p">()</code>'
    '</pre>'
)

EXPECTED = 'def handle(\n        event):\n    with uow:\n        uow.commit()'


def test_syntax_highlighted_pre_keeps_indentation(tmp_path):
    """O'Reilly-style highlighting puts each indent in its own whitespace-only text node between <code>
    spans; the XML parser collapsed those to a bare newline, leaving Python flush-left and meaningless."""
    units = _raw_units(tmp_path, HIGHLIGHTED_PRE)

    assert EXPECTED in [u['text'] for u in units]


def test_indent_without_newline_not_collapsed_to_one_space(tmp_path):
    """A whitespace-only node with no newline collapsed to a single space, so every depth read as one."""
    units = _raw_units(
        tmp_path,
        '<pre><code class="k">def</code> <code class="nf">f</code><code class="p">():</code>\n'
        '<code class="w"></code>    <code class="k">return</code> <code class="mi">1</code></pre>',
    )

    assert 'def f():\n    return 1' in [u['text'] for u in units]
