import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile, useVideoConfig} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

export type CoverProps = {
  background: string; // real frame from the job
  logo: string;
  hook: string; // big line
  sub: string; // small line under it
  brand: string;
};

export const coverDefaults: CoverProps = {
  background: 'board_cover_bg.jpg',
  logo: 'logo.jpg',
  hook: 'צבע לא מסתיר',
  sub: 'מה קורה לקיר לפני הצבע',
  brand: 'קולורטק · שפכטל · החלקת קירות · צבע',
};

const YELLOW = '#FFE600';

/**
 * Reel cover, 1080x1920. Everything important sits inside the 4:5 grid crop
 * (y 285..1635) so the thumbnail reads in the profile grid as well.
 */
export const Cover: React.FC<CoverProps> = (p) => {
  const {width, height} = useVideoConfig();
  useEffect(() => {
    loadHeebo();
  }, []);
  const font = `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`;
  const txt: React.CSSProperties = {fontFamily: font, fontWeight: 900, direction: 'rtl', textAlign: 'center'};
  return (
    <AbsoluteFill style={{backgroundColor: '#111'}} dir="rtl" lang="he">
      <Img
        src={staticFile(p.background)}
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'}}
      />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.30) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.65) 100%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: 200,
          left: '50%',
          width: 170,
          height: 170,
          borderRadius: '50%',
          overflow: 'hidden',
          transform: 'translateX(-50%)',
          border: '6px solid rgba(255,255,255,0.9)',
          boxShadow: '0 16px 40px rgba(0,0,0,0.45)',
          backgroundColor: '#fff',
        }}
      >
        <Img
          src={staticFile(p.logo)}
          style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
        />
      </div>
      <div style={{position: 'absolute', top: height * 0.50, left: 0, width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
        <div
          style={{
            ...txt,
            fontSize: 126,
            lineHeight: 1.05,
            color: '#fff',
            backgroundColor: 'rgba(0,0,0,0.78)',
            padding: '18px 60px 38px',
            borderRadius: 34,
            whiteSpace: 'nowrap',
          }}
        >
          {p.hook.split(' ').map((w, i) => (
            <span key={i} style={{color: i === p.hook.split(' ').length - 1 ? YELLOW : '#fff', margin: '0 0.14em'}}>
              {w}
            </span>
          ))}
        </div>
        <div
          style={{
            ...txt,
            fontSize: 62,
            color: '#111',
            backgroundColor: YELLOW,
            padding: '8px 44px 18px',
            borderRadius: 22,
            whiteSpace: 'nowrap',
          }}
        >
          {p.sub}
        </div>
      </div>
      <div style={{...txt, position: 'absolute', bottom: 110, width: '100%', fontSize: 38, color: 'rgba(255,255,255,0.9)', WebkitTextStroke: '6px #000', paintOrder: 'stroke fill'}}>
        {p.brand}
      </div>
    </AbsoluteFill>
  );
};
