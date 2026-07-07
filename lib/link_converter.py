import re

def convert_links(html):
    if not html:
        return html

    patterns = [
        r'https://kmmanohar1602\.blogspot\.com/\d{4}/\d{2}/([^"#?]+?)\.html(?:#more)?',
        r'https://www\.kmmanoharinsights\.com/\d{4}/\d{2}/([^"#?]+?)\.html(?:#more)?',
    ]

    for pattern in patterns:
        html = re.sub(
            pattern,
            lambda m: f'/{m.group(1)}/',
            html,
            flags=re.IGNORECASE,
        )

    return html