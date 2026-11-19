import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';
import {WA_GREEN, WhatsAppIcon} from './ViralReel';

const YELLOW = '#FFE600';
const OLIVE = '#3F4A22';

/**
 * Reel cover (1080x1920). The headline sits between 30 % and 62 % of the height so it
 * survives the 1:1 / 4:5 crop of the profile grid.
 */
export const Cover: React.FC = () => {
  useEffect(() => {
    loadHeebo();
  }, []);
  const font = `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`;
  const big: React.CSSProperties = {
    fontFamily: font,
    fontWeight: 900,
    direction: 'rtl',
    textAlign: 'center',
    lineHeight: 1.02,
    paintOrder: 'stroke fill',
    whiteSpace: 'nowrap',
  };
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <Img src={staticFile('kolortek_cover_bg.png')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.15) 22%, rgba(0,0,0,0.55) 40%, rgba(0,0,0,0.55) 62%, rgba(0,0,0,0.1) 78%, rgba(0,0,0,0.6) 100%)',
        }}
      />
      {/* badge */}
      <div
        style={{
          position: 'absolute',
          top: 120,
          left: '50%',
          width: 300,
          height: 300,
          transform: 'translateX(-50%)',
          borderRadius: '50%',
          overflow: 'hidden',
          border: '7px solid #fff',
          boxShadow: '0 16px 40px rgba(0,0,0,0.6)',
          backgroundColor: '#fff',
        }}
      >
        <Img src={staticFile('logo.jpg')} style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}} />
      </div>
      {/* kicker */}
      <div style={{position: 'absolute', top: 1920 * 0.31, width: '100%', display: 'flex', justifyContent: 'center'}}>
        <div
          dir="rtl"
          style={{
            fontFamily: font,
            fontWeight: 900,
            fontSize: 66,
            color: '#111',
            backgroundColor: YELLOW,
            padding: '6px 38px 14px',
            borderRadius: 20,
            transform: 'rotate(-3deg)',
            boxShadow: '0 10px 26px rgba(0,0,0,0.5)',
          }}
        >
          מהשלד ועד הגימור
        </div>
      </div>
      <div dir="rtl" style={{...big, position: 'absolute', top: 1920 * 0.385, width: '100%', fontSize: 200, color: '#fff', WebkitTextStroke: '18px #000', textShadow: '0 14px 30px rgba(0,0,0,0.7)'}}>
        נישת גבס
      </div>
      <div dir="rtl" style={{...big, position: 'absolute', top: 1920 * 0.5, width: '100%', fontSize: 150, color: YELLOW, WebkitTextStroke: '16px #000', textShadow: '0 14px 30px rgba(0,0,0,0.7)'}}>
        ישרה כמו סרגל
      </div>
      {/* bottom strip: brand + whatsapp */}
      <div
        style={{
          position: 'absolute',
          bottom: 210,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 22,
          padding: '18px 44px 22px',
          borderRadius: 999,
          backgroundColor: WA_GREEN,
          border: '5px solid #fff',
          boxShadow: '0 14px 34px rgba(0,0,0,0.55)',
          fontFamily: font,
          fontWeight: 900,
          fontSize: 70,
          color: '#fff',
          whiteSpace: 'nowrap',
          direction: 'ltr',
        }}
      >
        <WhatsAppIcon size={76} />
        <span>053-323-7036</span>
      </div>
      <div
        dir="rtl"
        style={{
          position: 'absolute',
          bottom: 110,
          width: '100%',
          textAlign: 'center',
          fontFamily: font,
          fontWeight: 900,
          fontSize: 50,
          color: '#fff',
          WebkitTextStroke: '7px ' + OLIVE,
          paintOrder: 'stroke fill',
        }}
      >
        קולורטק · עבודה עברית
      </div>
    </AbsoluteFill>
  );
};
