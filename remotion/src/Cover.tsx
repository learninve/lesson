import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

const YELLOW = '#FFE600';
const text: React.CSSProperties = {
  fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
  fontWeight: 900,
  direction: 'rtl',
  textAlign: 'center',
  WebkitTextStroke: '16px #000',
  paintOrder: 'stroke fill',
  textShadow: '0 12px 28px rgba(0,0,0,0.7)',
  whiteSpace: 'nowrap',
  position: 'absolute',
  width: '100%',
  lineHeight: 1.05,
};

/** Reels/TikTok cover: dirtiest-water frame, logo, 2-line hook kept inside the 4:5 / 1:1 grid crop. */
export const Cover: React.FC<{bg: string; logo: string; line1: string; line2: string; badge: string}> = ({
  bg,
  logo,
  line1,
  line2,
  badge,
}) => {
  useEffect(() => {
    loadHeebo();
  }, []);
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Img src={staticFile(bg)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.12)', transformOrigin: '45% 62%'}} />
      <AbsoluteFill
        style={{background: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.6) 100%)'}}
      />
      <Img
        src={staticFile(logo)}
        style={{position: 'absolute', top: 150, left: '50%', width: 300, height: 300, transform: 'translateX(-50%)', filter: 'drop-shadow(0 14px 28px rgba(0,0,0,0.6))'}}
      />
      <div dir="rtl" style={{...text, top: 560, fontSize: 150, color: '#FFFFFF'}}>
        {line1}
      </div>
      <div dir="rtl" style={{...text, top: 730, fontSize: 178, color: YELLOW}}>
        {line2}
      </div>
      <div
        dir="rtl"
        style={{
          position: 'absolute',
          top: 1330,
          left: '50%',
          transform: 'translateX(-50%) rotate(-3deg)',
          padding: '0px 54px 22px', lineHeight: 1.25,
          borderRadius: 28,
          backgroundColor: YELLOW,
          color: '#111',
          fontFamily: `${FONT_FAMILY}, sans-serif`,
          fontWeight: 900,
          fontSize: 84,
          whiteSpace: 'nowrap',
          boxShadow: '0 12px 30px rgba(0,0,0,0.55)',
        }}
      >
        {badge}
      </div>
    </AbsoluteFill>
  );
};
