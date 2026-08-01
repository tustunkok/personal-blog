from app.utils.markdown import render


def test_mermaid_fenced_block_renders_pre_tag():
    content = """```mermaid
flowchart TD
    A --> B
```
"""
    html = render(content)
    assert '<pre class="mermaid">' in html
    assert "flowchart TD" in html
    # text is HTML-escaped by the sanitizer but renders identically in the browser
    assert "A --&gt; B" in html


def test_non_mermaid_fenced_block_renders_code_tag():
    content = """```python
print("hello")
```
"""
    html = render(content)
    assert "<code" in html
    assert "print" in html
    assert "hello" in html


def test_math_blocks_still_render():
    content = """$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$"""
    html = render(content)
    assert "\\(" in html or "arithmatex" in html.lower()


def test_table_renders_html():
    content = """| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |
"""
    html = render(content)
    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th>Name</th>" in html
    assert "<td>Alice</td>" in html
