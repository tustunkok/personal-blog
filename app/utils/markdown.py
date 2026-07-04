import markdown


def render(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "fenced_code",
            "pymdownx.arithmatex",
        ],
        extension_configs={
            "pymdownx.arithmatex": {
                "generic": True,
            },
        },
    )
