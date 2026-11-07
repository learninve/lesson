import sys,subprocess,numpy as np
from PIL import Image
def render(txt,name):
    hdr=open('t.ass').read().split('[Events]')[0]+"[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    open(f'{name}.ass','w').write(hdr+"Dialogue: 0,0:00:00.00,0:00:05.00,Sub,,0,0,0,,{\\pos(540,400)}"+txt+"\n")
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=black:s=1080x1920','-vf',f'ass={name}.ass:fontsdir=fonts,crop=1080:200:0:300','-frames:v','1','-update','1',f'probe/{name}.png'],check=True)
    return np.array(Image.open(f'probe/{name}.png').convert('L')).astype(float)
def locate(full,tok):
    w=render(tok,'tok'); xs=np.where(w>200)[1]; t=w[:,xs.min():xs.max()+1]
    return min(((((full[:,x:x+t.shape[1]]-t)**2).mean(),x) for x in range(0,1080-t.shape[1])))
toks=sys.argv[2:]; full=render(sys.argv[1],'full')
print([(t,)+tuple(round(v) for v in locate(full,t)) for t in toks])
