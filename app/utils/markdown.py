import markdown


def _mermaid_formatter(
    src="", language="", class_name=None, options=None, md=None, **kwargs
):
    if language == "mermaid":
        return f'<pre class="mermaid">\n{src}\n</pre>'
    return None


def render(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "pymdownx.superfences",
            "pymdownx.arithmatex",
            "tables",
        ],
        extension_configs={
            "pymdownx.superfences": {
                "custom_fences": [
                    {
                        "name": "mermaid",
                        "class": "mermaid",
                        "format": _mermaid_formatter,
                    }
                ]
            },
            "pymdownx.arithmatex": {
                "generic": True,
            },
        },
    )
