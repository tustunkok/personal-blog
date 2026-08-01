import markdown
import nh3

# Allowlist of HTML elements produced by the markdown pipeline (and safe embeds
# such as mermaid `<pre class="mermaid">`). Everything else — <script>, <iframe>,
# event-handler attributes, javascript: URIs, etc. — is stripped by nh3.
_ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "code",
    "dd",
    "del",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "kbd",
    "li",
    "mark",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "div": {"class"},
    "td": {"align"},
    "th": {"align"},
    "ol": {"start"},
}

# Only safe URL schemes are kept in href/src; javascript:, data:, vbscript: etc.
# are dropped entirely.
_ALLOWED_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def _mermaid_formatter(
    src="", language="", class_name=None, options=None, md=None, **kwargs
):
    if language == "mermaid":
        return f'<pre class="mermaid">\n{src}\n</pre>'
    return None


def _sanitize(html: str) -> str:
    """Strip active content from rendered markdown.

    Python-Markdown passes raw HTML through unchanged, so without this every
    `| safe` template output (posts, pages, and *anonymous comments*) would be a
    stored-XSS sink. nh3 removes scripts, event handlers, dangerous URL schemes
    and non-allowlisted markup while preserving the safe markdown structure.
    """
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
    )


def render(content: str) -> str:
    html = markdown.markdown(
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
    return _sanitize(html)
