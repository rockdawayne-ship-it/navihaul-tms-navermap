"""E2E_매뉴얼_교육생용.md → E2E_매뉴얼_교육생용.html (단일 파일, 이미지 base64 내장).

실행: py -3.13 docs/build_html.py
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC = HERE / "E2E_매뉴얼_교육생용.md"
OUT = HERE / "E2E_매뉴얼_교육생용.html"

CSS = """
:root{--bg:#f6f7fb;--paper:#fff;--ink:#1b2430;--muted:#5f6b7a;--line:#e3e7ee;--accent:#03c75a;--accent-d:#02a84c;--note:#eef9f2;--warn:#fff4e5;--code:#f1f3f7;--side:280px}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font:15px/1.7 "Pretendard","Malgun Gothic",system-ui,sans-serif;color:var(--ink);background:var(--bg)}
nav.toc{position:fixed;top:0;left:0;bottom:0;width:var(--side);overflow:auto;background:#fff;border-right:1px solid var(--line);padding:20px 16px;font-size:13px}
nav.toc .brand{font-weight:800;font-size:16px;margin-bottom:4px}nav.toc .sub{color:var(--muted);font-size:12px;margin-bottom:14px}
nav.toc a{display:block;color:var(--ink);text-decoration:none;padding:4px 8px;border-radius:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
nav.toc a:hover{background:var(--code)}nav.toc a.l3{padding-left:22px;color:var(--muted);font-size:12px}
main{margin-left:var(--side);padding:40px 56px 80px;max-width:1040px}
article{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:40px 56px}
h1{font-size:30px;margin:0 0 8px;line-height:1.3}h2{font-size:22px;margin:48px 0 14px;padding-bottom:8px;border-bottom:2px solid var(--accent)}
h3{font-size:17px;margin:32px 0 10px}h4{font-size:15px;margin:24px 0 8px}
p{margin:10px 0}a{color:#2f6fed}
blockquote{margin:14px 0;padding:12px 16px;background:var(--note);border-left:4px solid var(--accent);border-radius:0 8px 8px 0}
blockquote p{margin:6px 0}blockquote pre{background:#fff;border:1px solid #cfe9d9}
blockquote.prompt{background:#eef3ff;border-left-color:#2f6fed}
code{font:13px/1.5 Consolas,"D2Coding",monospace;background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:12px 14px;overflow:auto}pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}th,td{border:1px solid var(--line);padding:7px 10px;vertical-align:top;text-align:left}th{background:var(--code)}
img{max-width:100%;border:1px solid var(--line);border-radius:8px;display:block;margin:16px auto 4px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
hr{border:0;border-top:1px solid var(--line);margin:40px 0}
.meta{color:var(--muted);font-size:13px;margin-bottom:20px}
.step{display:inline-block;background:var(--accent);color:#fff;font-weight:700;font-size:12px;padding:2px 8px;border-radius:999px;margin-right:6px;vertical-align:middle}
@media(max-width:960px){nav.toc{display:none}main{margin:0;padding:16px}article{padding:20px}}
@media print{nav.toc{display:none}main{margin:0;padding:0}article{border:0;box-shadow:none}h2{break-before:page}}
"""


def inline_images(html: str) -> str:
    def rep(m):
        p = HERE / m.group(1)
        if not p.exists():
            return m.group(0)
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'src="data:image/jpeg;base64,{b64}"'
    return re.sub(r'src="(images/[^"]+)"', rep, html)


def main() -> None:
    md_text = SRC.read_text(encoding="utf-8")
    # 프롬프트 박스(> **프롬프트 …**)를 별도 색으로
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "nl2br"], extension_configs={"toc": {"toc_depth": "2-3"}})
    body = md.convert(md_text)
    body = re.sub(r'<blockquote>\s*<p><strong>프롬프트', '<blockquote class="prompt">\n<p><strong>프롬프트', body)
    body = inline_images(body)
    toc = re.sub(r'<div class="toc">|</div>', "", md.toc)
    toc = toc.replace('<ul>', '', 1)[: -len('</ul>')] if toc.startswith('<ul>') else toc
    # TOC: 중첩 ul 을 평탄 링크로
    links = []
    for m in re.finditer(r'<li><a href="(#[^"]+)">([^<]+)</a>(\s*<ul>)?', toc):
        pass
    for lvl, m in _flatten(md.toc_tokens):
        links.append(f'<a class="l{lvl}" href="#{m["id"]}">{m["name"]}</a>')
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NaviHaul TMS E2E 매뉴얼</title><style>{CSS}</style></head>
<body>
<nav class="toc"><div class="brand">🚛 NaviHaul TMS</div><div class="sub">E2E 매뉴얼 · 교육생용</div>{''.join(links)}</nav>
<main><article>
{body}
</article></main>
</body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size//1024} KB, {len(links)} toc links)")


def _flatten(tokens, lvl=None):
    for t in tokens:
        yield t["level"], t
        yield from _flatten(t.get("children", []))


if __name__ == "__main__":
    main()
