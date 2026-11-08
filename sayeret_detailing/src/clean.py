import cv2, numpy as np, subprocess, sys
W,H=720,1280
raw=subprocess.run(['ffmpeg','-v','error','-i','raw.mp4','-f','rawvideo','-pix_fmt','bgr24','-'],capture_output=True).stdout
n=len(raw)//(W*H*3); fr=np.frombuffer(raw,np.uint8)[:n*W*H*3].reshape(n,H,W,3).copy()
def seg_mask(a,b,box,th=205):
    x0,x1,y0,y1=box
    g=np.stack([cv2.cvtColor(fr[i,y0:y1,x0:x1],cv2.COLOR_BGR2GRAY) for i in range(a,b)])
    m=((g>th).mean(0)>0.95).astype(np.uint8)*255
    full=np.zeros((H,W),np.uint8); full[y0:y1,x0:x1]=m; return full
mA=seg_mask(0,44,(90,640,440,530)); mB=seg_mask(44,112,(230,490,470,535))
# emoji: yellow-ish static blob at right end of A
x0,x1,y0,y1=560,640,440,530
hsv=np.stack([cv2.cvtColor(fr[i,y0:y1,x0:x1],cv2.COLOR_BGR2HSV) for i in range(0,44)])
yel=((hsv[...,0]>15)&(hsv[...,0]<40)&(hsv[...,1]>90)&(hsv[...,2]>150)).mean(0)>0.9
e=np.zeros((H,W),np.uint8); e[y0:y1,x0:x1]=yel*255; mA=cv2.bitwise_or(mA,cv2.dilate(e,np.ones((15,15),np.uint8)))
k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15))
mA=cv2.dilate(mA,k,iterations=1); mB=cv2.dilate(mB,k,iterations=1)
cv2.imwrite('maskA.png',mA); cv2.imwrite('maskB.png',mB)
print('mask px',int((mA>0).sum()),int((mB>0).sum()))
OW,OH=1080,1920; TOTAL=372
out=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','30','-i','-',
  '-c:v','libx264','-crf','8','-preset','fast','-pix_fmt','yuv420p','base_video.mp4'],stdin=subprocess.PIPE)
def zoomed(f,i):
    z=1.0+0.08*min(i,TOTAL-1)/(TOTAL-1)
    s=1.5*z
    M=np.float32([[s,0,OW/2-s*W/2],[0,s,OH/2-s*H/2]])
    return cv2.warpAffine(f,M,(OW,OH),flags=cv2.INTER_LANCZOS4,borderMode=cv2.BORDER_REPLICATE)
last=None
for i in range(n):
    f=fr[i]
    m = mA if i<44 else (mB if i<112 else None)
    if m is not None:
        g=cv2.inpaint(f,m,9,cv2.INPAINT_NS)
        # neutralise chroma blotches: replace Cr/Cb in the hole with a masked local mean of the surroundings
        ycc=cv2.cvtColor(g,cv2.COLOR_BGR2YCrCb).astype(np.float32); src=cv2.cvtColor(f,cv2.COLOR_BGR2YCrCb).astype(np.float32)
        ok=(cv2.dilate(m,np.ones((41,41),np.uint8))>0)&(m==0); okf=ok.astype(np.float32)
        den=cv2.GaussianBlur(okf,(0,0),14)+1e-6
        for c in (1,2):
            loc=cv2.GaussianBlur(src[...,c]*okf,(0,0),14)/den
            soft=(cv2.GaussianBlur(m,(0,0),4)/255.0)
            ycc[...,c]=ycc[...,c]*(1-soft)+loc*soft
        g=cv2.cvtColor(np.clip(ycc,0,255).astype(np.uint8),cv2.COLOR_YCrCb2BGR)
        nz=np.random.default_rng(i).normal(0,5,g.shape)
        mm=(cv2.GaussianBlur(m,(0,0),3)/255.0)[...,None]
        f=np.clip(g+nz*mm,0,255).astype(np.uint8)
    last=zoomed(f,i); out.stdin.write(last.tobytes())
for i in range(n,TOTAL):
    last=zoomed(fr[n-1],i); out.stdin.write(last.tobytes())
cv2.imwrite('freeze.png',last)
out.stdin.close(); out.wait()
