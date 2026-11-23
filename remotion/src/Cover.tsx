import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

export type CoverData = {bg: string; logo: string; line1: string; line2: string; tag: string};

const YELLOW = '#FFE600';

/**
 * 1080x1920 cover. Everything important (logo, headline, tag) sits inside the centre
 * 1080x1350 area, so the Instagram grid crop (4:5) and the TikTok profile crop keep it.
 */
export const Cover: React.FC<{data: CoverData}> = ({data}) => {
  useEffect(() => {
    loadHeebo();
  }, []);
  const text: React.CSSProperties = {
    fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
    fontWeight: 900,
    direction: 'rtl',
    textAlign: 'center',
    whiteSpace: 'nowrap',
    width: '100%',
    position: 'absolute',
    left: 0,
    lineHeight: 1,
    paintOrder: 'stroke fill',
    textShadow: '0 12px 26px rgba(0,0,0,0.7)',
  };
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Img
        src={staticFile(data.bg)}
        style={{width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.12)', transformOrigin: '35% 40%'}}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.78) 68%, rgba(0,0,0,0.85) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 330,
          left: '50%',
          width: 250,
          height: 250,
          marginLeft: -125,
          borderRadius: '50%',
          overflow: 'hidden',
          border: '6px solid rgba(255,255,255,0.92)',
          backgroundColor: '#fff',
          boxShadow: '0 14px 34px rgba(0,0,0,0.55)',
        }}
      >
        <Img
          src={staticFile(data.logo)}
          style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
        />
      </div>
      <div dir="rtl" style={{...text, top: 1030, fontSize: 170, color: '#fff', WebkitTextStroke: '18px #000'}}>
        {data.line1}
      </div>
      <div dir="rtl" style={{...text, top: 1215, fontSize: 178, color: YELLOW, WebkitTextStroke: '18px #000'}}>
        {data.line2}
      </div>
      <div style={{position: 'absolute', top: 1445, left: 0, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <div
          dir="rtl"
          style={{
            fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
            fontWeight: 900,
            fontSize: 66,
            lineHeight: 1,
            color: '#111',
            backgroundColor: YELLOW,
            padding: '16px 44px 22px',
            borderRadius: 22,
            boxShadow: '0 10px 26px rgba(0,0,0,0.5)',
          }}
        >
          {data.tag}
        </div>
      </div>
    </AbsoluteFill>
  );
};
