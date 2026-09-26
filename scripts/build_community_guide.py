"""Rebuild the maintained community guide (reportlab and Pillow required)."""
from pathlib import Path
import base64
import html
import json
import os
import re
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from community_guide_content import PAGES, REPO, RELEASE

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'artifacts/community-guide'
SHOTS = ROOT / 'docs/images'
PDF = ROOT / 'output/pdf/SoundShredder-Higgsfield-Community-Guide.pdf'
HTML = ROOT / 'output/html/SoundShredder-Higgsfield-Community-Guide.html'
for folder in (WORK, PDF.parent, HTML.parent): folder.mkdir(parents=True, exist_ok=True)

BG = '#08121c'; PANEL = '#112330'; LINE = '#2a414e'; MINT = '#79f6d3'; TEXT = '#e8f2f5'; MUTED = '#a4bac7'
W, H, M = 595.276, 841.89, 42
CW = W - 2*M
pdfmetrics.registerFont(TTFont('Space', str(ROOT/'static/fonts/SpaceGrotesk-Variable.ttf')))
font_dir = Path(os.environ.get('SOUNDSHREDDER_DOC_FONT_DIR', 'C:/Windows/Fonts'))
if not (font_dir/'segoeui.ttf').exists():
    raise RuntimeError('Set SOUNDSHREDDER_DOC_FONT_DIR to a folder containing segoeui.ttf and segoeuib.ttf.')
pdfmetrics.registerFont(TTFont('Body', str(font_dir/'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('BodyBold', str(font_dir/'segoeuib.ttf')))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='Body', boldItalic='BodyBold')
styles = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=10.2, leading=14.4, textColor=colors.HexColor(TEXT)),
    'small': ParagraphStyle('small', fontName='Body', fontSize=8.1, leading=11.4, textColor=colors.HexColor(MUTED)),
    'card': ParagraphStyle('card', fontName='Body', fontSize=9.4, leading=13.1, textColor=colors.HexColor(TEXT)),
    'table': ParagraphStyle('table', fontName='Body', fontSize=8.9, leading=12.0, textColor=colors.HexColor(TEXT)),
    'label': ParagraphStyle('label', fontName='BodyBold', fontSize=9, leading=12.2, textColor=colors.HexColor(MINT)),
}


def para(c, text, x, y, width, style='body'):
    q = Paragraph(text, styles[style])
    _, height = q.wrap(width, 1000)
    q.drawOn(c, x, H-y-height)
    return y + height


def rect(c, x, y, width, height, fill=PANEL, stroke=LINE, radius=8):
    c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(colors.HexColor(stroke)); c.setLineWidth(.65)
    c.roundRect(x, H-y-height, width, height, radius, stroke=1, fill=1)


def figure(c, name, caption, x, y, width, maxh):
    path = SHOTS/(name+'.png'); iw, ih = Image.open(path).size
    factor = min(width/iw, maxh/ih)
    dw, dh = iw*factor, ih*factor
    c.drawImage(str(path), x+(width-dw)/2, H-y-dh, width=dw, height=dh, mask='auto')
    y += dh + 6
    return para(c, caption, x, y, width, 'small') + 13


def draw_cards(c, items, x, y, width):
    gap=12; col=(width-gap)/2
    for offset in range(0,len(items),2):
        heights=[]
        for title,text in items[offset:offset+2]:
            h1=Paragraph(title,styles['label']).wrap(col-24,1000)[1]
            h2=Paragraph(text,styles['card']).wrap(col-24,1000)[1]
            heights.append(h1+h2+31)
        rh=max(heights)
        for idx,(title,text) in enumerate(items[offset:offset+2]):
            cx=x+idx*(col+gap);rect(c,cx,y,col,rh)
            cy=para(c,title,cx+12,y+11,col-24,'label')+6
            para(c,text,cx+12,cy,col-24,'card')
        y+=rh+10
    return y+1


def draw_block(c,b,x,y,width):
    kind=b['type']
    if kind=='p': return para(c,b['text'],x,y,width)+11
    if kind=='figure': return figure(c,b['name'],b['caption'],x,y,width,b['maxh'])
    if kind=='cards': return draw_cards(c,b['items'],x,y,width)
    if kind=='note':
        label=Paragraph(b['title'],styles['label']).wrap(width-30,1000)[1]
        body=Paragraph(b['text'],styles['card']).wrap(width-30,1000)[1]
        height=label+body+33
        rect(c,x,y,width,height,fill='#11312f',stroke='#326c5b')
        cy=para(c,b['title'],x+15,y+12,width-30,'label')+7
        para(c,b['text'],x+15,cy,width-30,'card')
        return y+height+13
    if kind=='steps':
        for i,(title,text) in enumerate(b['items'],1):
            c.setFillColor(colors.HexColor(MINT));c.circle(x+9,H-y-9,9,stroke=0,fill=1)
            c.setFillColor(colors.HexColor(BG));c.setFont('BodyBold',9);c.drawCentredString(x+9,H-y-12,str(i))
            cy=para(c,title,x+28,y,width-28,'label')+4
            y=para(c,text,x+28,cy,width-28,'card')+12
        return y
    if kind=='table':
        rows=[[Paragraph(html.escape(s),styles['label']) for s in b['headers']]]
        rows.extend([Paragraph(s,styles['table']) for s in row] for row in b['rows'])
        widths=[width*.24,width*.28,width*.48] if len(b['headers'])==3 else [width*.31,width*.69]
        t=Table(rows,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183a3b')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#10212c'),colors.HexColor('#0c1b25')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
            ('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor(LINE))]))
        _,height=t.wrap(width,1000);t.drawOn(c,x,H-y-height)
        return y+height+14
    if kind=='flow':
        gap=10; col=(width-2*gap)/3
        for i,(title,text) in enumerate(b['items']):
            cx=x+i*(col+gap);rect(c,cx,y,col,66,fill='#152932')
            cy=para(c,title,cx+12,y+12,col-24,'label')+7
            para(c,text,cx+12,cy,col-24,'card')
        return y+81
    if kind=='sidebar':
        left=122; iw,ih=Image.open(SHOTS/(b['name']+'.png')).size; dh=left*ih/iw
        c.drawImage(str(SHOTS/(b['name']+'.png')),x,H-y-dh,width=left,height=dh,mask='auto')
        bottom=para(c,b['caption'],x,y+dh+7,left,'small')
        cy=y
        for title,text in b['items']:
            cy=para(c,title,x+left+23,cy,width-left-23,'label')+6
            cy=para(c,text,x+left+23,cy,width-left-23,'card')+14
        return max(cy,bottom)+9
    raise ValueError(kind)


def build_pdf():
    c=Canvas(str(PDF),pagesize=(W,H));c.setTitle('SoundShredder | Higgsfield Community Guide');c.setAuthor('cyr4x')
    qa=[]
    for index,page in enumerate(PAGES,1):
        c.bookmarkPage(page['id'])
        c.addOutlineEntry(page['title'].replace('\n',' '),page['id'],level=0)
        c.setFillColor(colors.HexColor(BG));c.rect(0,0,W,H,stroke=0,fill=1)
        c.setStrokeColor(colors.HexColor(LINE));c.line(M,H-49,W-M,H-49)
        c.setFillColor(colors.HexColor(MINT));c.setFont('BodyBold',8.7);c.drawString(M,H-32,'SOUNDSHREDDER / CYR4X')
        c.setFont('Body',8.1);c.setFillColor(colors.HexColor(MUTED));c.drawRightString(W-M,H-32,'HIGGSFIELD COMMUNITY GUIDE')
        y=66
        y=para(c,page['label'],M,y,CW,'label')+12
        title=Paragraph(page['title'].replace('\n','<br/>'),ParagraphStyle('title',fontName='Space',fontSize=40 if page.get('cover') else 29,leading=43 if page.get('cover') else 34,textColor=colors.HexColor(TEXT)))
        _,th=title.wrap(CW,1000);title.drawOn(c,M,H-y-th);y+=th+16
        if page.get('cover'):
            c.drawImage(str(SHOTS/'higgsfield-mark.png'),W-M-22,H-84,width=22,height=22,mask='auto')
        for b in page['blocks']: y=draw_block(c,b,M,y,CW)
        qa.append({'page':index,'content_bottom':round(y,1),'limit':H-47})
        c.setStrokeColor(colors.HexColor(LINE));c.line(M,35,W-M,35)
        c.setFont('Body',7.2);c.setFillColor(colors.HexColor(MUTED));c.drawString(M,22,'v1.3.0  /  UPDATED SEPTEMBER 26, 2026  /  MADE BY CYR4X')
        c.drawRightString(W-M,22,f'{index:02d} / {len(PAGES):02d}')
        c.showPage()
    c.save();(WORK/'layout-check.json').write_text(json.dumps(qa,indent=2))
    overflow=[q for q in qa if q['content_bottom']>q['limit']]
    if overflow: raise RuntimeError(f'Layout overflow: {overflow}')


def embed(path,mime): return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()
def htmltext(text):
    text=re.sub(r'<link href="([^"]+)"(?: color="[^"]+")?>',r'<a href="\1" target="_blank" rel="noopener noreferrer">',text)
    return text.replace('</link>','</a>')


def htmlblock(b):
    kind=b['type']
    if kind=='p': return '<p>'+htmltext(b['text'])+'</p>'
    if kind=='figure': return f'<figure><img src="{embed(SHOTS/(b["name"]+".png"),"image/png")}" alt="{html.escape(b["caption"])}" loading="lazy"><figcaption>{b["caption"]}</figcaption></figure>'
    if kind=='cards': return '<div class="cards">'+''.join('<div class="card"><h3>'+title+'</h3><p>'+htmltext(text)+'</p></div>' for title,text in b['items'])+'</div>'
    if kind=='note': return '<aside class="note"><h3>'+b['title']+'</h3><p>'+htmltext(b['text'])+'</p></aside>'
    if kind=='steps': return '<ol class="steps">'+''.join('<li><h3>'+title+'</h3><p>'+htmltext(text)+'</p></li>' for title,text in b['items'])+'</ol>'
    if kind=='table': return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in b['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+htmltext(s)+'</td>' for s in row)+'</tr>' for row in b['rows'])+'</tbody></table></div>'
    if kind=='flow': return '<div class="flow">'+''.join('<div><h3>'+title+'</h3><p>'+text+'</p></div>' for title,text in b['items'])+'</div>'
    if kind=='sidebar': return '<div class="sidebar-example"><figure><img src="'+embed(SHOTS/(b['name']+'.png'),'image/png')+'" alt="Desktop session sidebar"><figcaption>'+b['caption']+'</figcaption></figure><div>'+''.join('<section><h3>'+title+'</h3><p>'+htmltext(text)+'</p></section>' for title,text in b['items'])+'</div></div>'
    raise ValueError(kind)


def build_html():
    css='''
@font-face{font-family:Space;src:url(FONTDATA) format('truetype');font-weight:300 700;font-display:swap}
:root{color-scheme:dark;--bg:#08121c;--panel:#112330;--line:#2a414e;--mint:#79f6d3;--ink:#e8f2f5;--muted:#a4bac7}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 'Segoe UI',Arial,sans-serif}a{color:var(--mint);text-underline-offset:4px}b{font-weight:650}button{font:inherit}button,a{touch-action:manipulation}a:focus-visible,button:focus-visible{outline:3px solid var(--mint);outline-offset:5px}
.masthead{border-bottom:1px solid var(--line);padding:24px max(24px,calc((100vw - 1040px)/2));display:flex;gap:24px;align-items:center;justify-content:space-between;background:#0c1c26}.brand{font:700 18px Space,sans-serif;letter-spacing:-.5px}.community{display:flex;align-items:center;gap:9px;font:500 13px Space,sans-serif;color:var(--muted)}.community img{width:24px;height:24px}.masthead small{color:var(--mint)}
.shell{max-width:1100px;margin:auto;padding:40px 30px 70px}.intro-meta{display:flex;gap:12px;flex-wrap:wrap;font:11px Space,sans-serif;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin-bottom:28px}.intro-meta span{padding:7px 10px;border:1px solid var(--line);border-radius:30px}.toc{padding:24px;background:var(--panel);border:1px solid var(--line);border-radius:16px;margin:30px 0 70px}.toc strong{font:600 14px Space}.toc nav{display:grid;grid-template-columns:repeat(4,1fr);gap:12px 20px;margin-top:18px}.toc a{font-size:13px;text-decoration:none}.toc a:hover{text-decoration:underline}.guide-page{padding:0 0 55px;margin:0 0 55px;border-bottom:1px solid var(--line)}.eyebrow{font:600 11px Space;letter-spacing:2px;color:var(--mint);margin-bottom:15px}h1,h2,h3{font-family:Space,sans-serif;margin-top:0}h1{font-size:clamp(42px,6.5vw,76px);font-weight:500;letter-spacing:-3px;line-height:1.05;margin-bottom:26px}h2{font-size:clamp(30px,4vw,43px);font-weight:500;letter-spacing:-1.5px;line-height:1.16;margin-bottom:26px}h3{font-size:16px;line-height:1.45;color:var(--mint);font-weight:600;margin:0 0 10px}p{margin:0 0 22px;overflow-wrap:anywhere}.guide-page>p:first-of-type{font-size:18px;color:#bfd2dc;max-width:930px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:25px 0}.card{padding:24px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(130deg,#17333b70,var(--panel))}.card p,.note p{margin:0;font-size:15px}figure{margin:30px 0}figure>img{display:block;width:100%;height:auto;border-radius:12px;border:1px solid var(--line)}figcaption{font-size:12px;line-height:1.6;color:var(--muted);margin-top:11px}.note{border:1px solid #326c5b;border-radius:12px;background:#11312f;padding:24px 28px;margin:25px 0}.steps{list-style:none;padding:0;counter-reset:step;margin:25px 0}.steps li{counter-increment:step;padding:0 0 6px 52px;position:relative}.steps li:before{content:counter(step);position:absolute;left:0;top:0;width:30px;height:30px;border-radius:50%;background:var(--mint);color:#072820;text-align:center;line-height:30px;font-weight:700}.steps p{font-size:15px}.table-wrap{overflow:auto;margin:28px 0}table{width:100%;border-collapse:collapse;font-size:14px}th{font:600 12px Space;color:var(--mint);background:#183a3b;text-align:left;letter-spacing:.5px}td,th{padding:16px;border-bottom:1px solid var(--line);vertical-align:top}tr:nth-child(odd){background:#10212c}tr:nth-child(even){background:#0c1b25}.flow{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:26px 0}.flow>div{padding:24px 20px;background:#152932;border:1px solid var(--line);border-radius:10px}.flow p{margin:0;font-size:14px}.sidebar-example{display:grid;grid-template-columns:230px 1fr;gap:40px;margin:25px 0}.sidebar-example figure{margin:0}.sidebar-example section{margin-bottom:24px}.sidebar-example p{font-size:15px}.page-tail{font:11px Space;color:var(--muted);text-align:right;margin-top:25px}.endnote{font-size:12px;color:var(--muted)}.utility{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.utility a,.utility button{border:1px solid #42685f;border-radius:7px;padding:10px 16px;background:#17372f;color:var(--mint);font-size:13px;text-decoration:none;cursor:pointer}.top-link{font-size:12px;display:inline-block;margin-top:20px}
@media(max-width:700px){.shell{padding:28px 18px 45px}.masthead{padding:20px;align-items:flex-start;flex-direction:column;gap:8px}.cards,.sidebar-example{grid-template-columns:1fr}.sidebar-example figure{max-width:230px}.toc nav{grid-template-columns:1fr 1fr}.card,.note{padding:20px}.flow{grid-template-columns:1fr}.guide-page{margin-bottom:40px;padding-bottom:35px}td,th{padding:12px;font-size:12px}h1{letter-spacing:-1.5px}.community{font-size:12px}.guide-page>p:first-of-type{font-size:16px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{.toc,.utility,.top-link{display:none}.shell{padding:0}.guide-page{break-before:page;break-inside:avoid;margin:0;padding:20px}.masthead{padding:20px}body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''.replace('FONTDATA',embed(ROOT/'static/fonts/SpaceGrotesk-Variable.ttf','font/ttf'))
    nav=''.join(f'<a href="#{q["id"]}">{i+1:02d} / {html.escape(q["title"].replace(chr(10)," "))}</a>' for i,q in enumerate(PAGES))
    content=[]
    for i,q in enumerate(PAGES):
        tag='h1' if q.get('cover') else 'h2'
        title=html.escape(q['title']).replace('\n','<br>')
        repair = ''
        if q['id'] == 'mac-troubleshooting':
            repair_url = embed(ROOT/'support/mac/SoundShredder-Mac-Certificate-Fix.zip','application/zip')
            repair = f'<div class="utility"><a href="{repair_url}" download="SoundShredder-Mac-Certificate-Fix.zip">Download Mac certificate repair launcher</a></div>'
        content.append(f'<article class="guide-page" id="{q["id"]}"><div class="eyebrow">{q["label"]}</div><{tag}>{title}</{tag}>'+''.join(htmlblock(b) for b in q['blocks'])+repair+f'<div class="page-tail">SOUNDSHREDDER / {i+1:02d}</div></article>')
        if i==0: content.append('<div class="toc"><strong>YOUR GUIDE AT A GLANCE</strong><nav>'+nav+'</nav></div>')
    footer=f'''<div class="utility"><a href="{RELEASE}" target="_blank" rel="noopener noreferrer">Download SoundShredder</a><a href="{REPO}" target="_blank" rel="noopener noreferrer">GitHub project</a><button type="button" onclick="window.print()">Print this guide</button></div><p class="endnote" style="margin-top:24px">Guide updated for SoundShredder 1.3.0 on September 26, 2026. Akira screenshots show a real completed source-app session; Electron shares the workspace. The bubble panel is a separate settings example. Screenshots demonstrate controls, not guaranteed audio quality. The source video and extracted audio are not distributed. Community-created by cyr4x; not an official Higgsfield product. Higgsfield branding belongs to its owner. Space Grotesk is used under the SIL Open Font License.</p><a class="top-link" href="#top">Back to top</a>'''
    doc=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="author" content="cyr4x"><title>SoundShredder | Higgsfield Community Guide</title><style>{css}</style></head><body id="top"><header class="masthead"><div class="brand">SoundShredder <small>/ cyr4x</small></div><div class="community"><img src="{embed(ROOT/'static/higgsfield-mark.svg','image/svg+xml')}" alt="Higgsfield logo">Made for the Higgsfield Community</div></header><main class="shell"><div class="intro-meta"><span>Community field guide</span><span>v1.3.0 Electron desktop</span><span>Windows + Mac</span><span>CPU + NVIDIA GPU</span></div>{''.join(content)}{footer}</main></body></html>'''
    font_license=html.escape('\n'.join(line.rstrip() for line in (ROOT/'static/fonts/SpaceGrotesk-OFL.txt').read_text(encoding='utf-8').splitlines()))
    doc=doc.replace('</body>',f'<template id="space-grotesk-license"><pre>{font_license}</pre></template></body>')
    HTML.write_text(doc,encoding='utf-8')


if __name__=='__main__':
    build_pdf();build_html()
    print(PDF);print(HTML)
