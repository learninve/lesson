import os, sys, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H=1080,1920
PHONE=os.environ.get('PHONE','[05X-XXXXXXX]')
IG='@sayeret.detailing'
HEEBO='Heebo.ttf'
EMOJI='/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
SAFE_L,SAFE_R,SAFE_B=120,960,1670   # no text outside x∈[120,960], y<=1670
MAXW=SAFE_R-SAFE_L
def font(size,w=800):
    f=ImageFont.truetype(HEEBO,size,layout_engine=ImageFont.Layout.RAQM); f.set_variation_by_axes([w]); return f
def split_emoji(t):
    m=re.search(r'\s*([\U0001F300-\U0001FAFF])\s*$',t)
    return (t[:m.start()],m.group(1)) if m else (t,None)
def emoji_img(ch,h):
    f=ImageFont.truetype(EMOJI,109); im=Image.new('RGBA',(160,160),(0,0,0,0))
    ImageDraw.Draw(im).text((10,10),ch,font=f,embedded_color=True)
    im=im.crop(im.getbbox()); r=h/im.height; return im.resize((max(1,int(im.width*r)),h),Image.LANCZOS)
def wlen(f,t,stroke): return f.getlength(t,direction='rtl',language='he') if re.search('[֐-׿]',t) else f.getlength(t)
def wrap(words,f,maxw,stroke):
    lines=[];cur=[]
    for w in words:
        t=' '.join(cur+[w])
        if cur and wlen(f,t,stroke)+2*stroke>maxw: lines.append(' '.join(cur)); cur=[w]
        else: cur.append(w)
    if cur: lines.append(' '.join(cur))
    k=len(lines)
    if k>1:  # rebalance: same line count, minimise the widest line
        import itertools
        best=None
        for cuts in itertools.combinations(range(1,len(words)),k-1):
            idx=(0,)+cuts+(len(words),)
            ls=[' '.join(words[idx[j]:idx[j+1]]) for j in range(k)]
            mw=max(wlen(f,l,stroke) for l in ls)
            if mw+2*stroke<=maxw and (best is None or mw<best[0]): best=(mw,ls)
        if best: lines=best[1]
    return lines
def draw_line(layer,cx,y,t,f,fill,stroke,emoji=None,shadow=True):
    d=ImageDraw.Draw(layer)
    he=bool(re.search('[֐-׿]',t)); kw=dict(direction='rtl',language='he') if he else {}
    bb=d.textbbox((0,0),t,font=f,stroke_width=stroke,**kw); tw=bb[2]-bb[0]
    eh=int(f.size*0.95); em=emoji_img(emoji,eh) if emoji else None
    gap=int(f.size*0.2); total=tw+((em.width+gap) if em else 0)
    # RTL: trailing emoji sits at the visual LEFT end of the line
    x0=cx-total//2
    tx=x0+((em.width+gap) if em else 0)-bb[0]
    if shadow:
        sh=Image.new('RGBA',layer.size,(0,0,0,0)); sd=ImageDraw.Draw(sh)
        sd.text((tx+3,y+6),t,font=f,fill=(0,0,0,170),stroke_width=stroke,stroke_fill=(0,0,0,170),**kw)
        layer.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    d=ImageDraw.Draw(layer)
    d.text((tx,y),t,font=f,fill=fill,stroke_width=stroke,stroke_fill=(0,0,0,255),**kw)
    if em: layer.alpha_composite(em,(x0,y+int((bb[3]-bb[1]-eh)/2)+bb[1]))
    return bb[3]-bb[1]
def block(text,size,stroke,cy=None,bottom=None,fill=(255,255,255,255),lh=1.28,name='x'):
    body,emo=split_emoji(text); f=font(size)
    lines=wrap(body.split(),f,MAXW-(int(size*1.2) if emo else 0),stroke)
    layer=Image.new('RGBA',(W,H),(0,0,0,0)); step=int(size*lh); total=step*len(lines)
    top=(cy-total//2) if cy is not None else (bottom-total)
    assert top>=0 and top+total<=SAFE_B,(name,top,total)
    for i,l in enumerate(lines):
        draw_line(layer,540,top+i*step,l,f,fill,stroke,emoji=emo if i==len(lines)-1 else None)
    layer.save(f'L_{name}.png'); print(name,lines,'y',top,top+total); return layer
if __name__=='__main__':
    block('ככה נראה רכב אחרי שנה בלי ניקוי 😬',92,8,cy=430,name='hook')
    caps=['שטיחים, מתחת למושבים, כל פינה','חול, פירורים, כתמים – הכל יוצא','ניקוי עמוק + חידוש ריפודים במכונת שאיבה מקצועית','תגידו שלום ללכלוך 👋']
    for i,c in enumerate(caps): block(c,76,7,bottom=1290,name=f'cap{i+1}')
    # end card
    L=Image.new('RGBA',(W,H),(0,0,0,0))
    logo=Image.open('logo.png').resize((440,440),Image.LANCZOS); L.alpha_composite(logo,(320,210))
    f=font(124); draw_line(L,540,700,'סיירת דיטיילינג',f,(255,255,255,255),8)
    draw_line(L,540,880,'ניקוי פנים רכב וחידוש ריפודים',font(62,700),(255,255,255,255),6)
    # phone pill
    fp=font(98,800); d=ImageDraw.Draw(L); bb=d.textbbox((0,0),PHONE,font=fp)
    pw=bb[2]-bb[0]+80; ph=150; px=540-pw//2; py=1040
    assert px>=SAFE_L-40 and px+pw<=SAFE_R+40,(px,pw)
    d.rounded_rectangle([px,py,px+pw,py+ph],radius=85,fill=(18,150,215,255),outline=(255,255,255,255),width=6)
    d.text((540-(bb[2]+bb[0])//2,py+ph//2-(bb[3]+bb[1])//2),PHONE,font=fp,fill=(255,255,255,255))
    draw_line(L,540,1260,IG,font(72,700),(150,220,255,255),6)
    draw_line(L,540,1410,'מגיעים עד אליך',font(58,700),(255,255,255,255),5,emoji='🚗')
    L.save('L_endcard.png'); print('endcard ok')
