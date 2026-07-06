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
    assert "A --> B" in html


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
