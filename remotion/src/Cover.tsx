import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

const YELLOW = '#FFE600';

/** Reel cover (1080x1920). Everything important sits inside the central 1080x1350 area so the 4:5 grid crop keeps it. */
export const Cover: React.FC<{bg: string; logo: string; line1: string; line2: string; tag: string; phone: string}> = ({
  bg,
  logo,
  line1,
  line2,
  tag,
  phone,
}) => {
  useEffect(() => {
    loadHeebo();
  }, []);
  const text: React.CSSProperties = {
    fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
    fontWeight: 900,
    direction: 'rtl',
    textAlign: 'center',
    width: '100%',
    position: 'absolute',
    whiteSpace: 'nowrap',
    WebkitTextStroke: '16px #000',
    paintOrder: 'stroke fill',
    textShadow: '0 12px 26px rgba(0,0,0,0.7)',
  };
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Img src={staticFile(bg)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(20,28,12,0.78) 0%, rgba(20,28,12,0.35) 30%, rgba(0,0,0,0) 48%, rgba(0,0,0,0) 62%, rgba(20,28,12,0.88) 86%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 330,
          left: '50%',
          width: 300,
          height: 300,
          marginLeft: -150,
          borderRadius: '50%',
          overflow: 'hidden',
          border: '8px solid rgba(255,255,255,0.92)',
          boxShadow: '0 18px 44px rgba(0,0,0,0.6)',
          backgroundColor: '#fff',
        }}
      >
        <Img
          src={staticFile(logo)}
          style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
        />
      </div>
      <div dir="rtl" style={{...text, top: 650, fontSize: 190, lineHeight: 1.1, color: '#fff'}}>
        {line1}
      </div>
      <div dir="rtl" style={{...text, top: 850, fontSize: 190, lineHeight: 1.1, color: YELLOW}}>
        {line2}
      </div>
      <div style={{position: 'absolute', top: 1340, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <div
          dir="rtl"
          style={{
            fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
            fontWeight: 900,
            fontSize: 62,
            color: '#111',
            backgroundColor: YELLOW,
            padding: '6px 44px 12px',
            borderRadius: 26,
            boxShadow: '0 10px 26px rgba(0,0,0,0.5)',
          }}
        >
          {tag}
        </div>
      </div>
      <div dir="ltr" style={{...text, top: 1470, fontSize: 112, color: '#fff', letterSpacing: '0.04em', WebkitTextStroke: '12px #000'}}>
        {phone}
      </div>
    </AbsoluteFill>
  );
};
