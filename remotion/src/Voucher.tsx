import React, {useEffect} from 'react';
import {AbsoluteFill, Img, staticFile, useVideoConfig} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

export type VoucherProps = {
  background: string; // file in public/ (a real frame from the job)
  logo: string;
  eyebrow: string; // "שובר הטבה"
  benefit: string; // the big line
  benefitSub: string; // what it applies to
  terms: string[]; // small print, one per line
  code: string;
  validUntil: string;
  contactName: string;
  phone: string;
  brand: string;
};

export const voucherDefaults: VoucherProps = {
  background: 'board_result.jpg',
  logo: 'logo.jpg',
  eyebrow: 'שובר הטבה',
  benefit: '₪300 הנחה',
  benefitSub: 'על עבודת שפכטל + צבע לדירה',
  terms: [
    'בהצגת השובר לפני סגירת הצעת המחיר',
    'שובר אחד לעבודה · לא ניתן לצבירה',
    'עבודה מ-₪6,000 ומעלה',
  ],
  code: 'קיר-חלק',
  validUntil: '31.12.2026',
  contactName: 'ליאב',
  phone: '053-3237036',
  brand: 'קולורטק · שפכטל, החלקת קירות, צבע וגבס',
};

const YELLOW = '#FFE600';
const font = `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`;

export const Voucher: React.FC<VoucherProps> = (p) => {
  const {width, height} = useVideoConfig();
  useEffect(() => {
    loadHeebo();
  }, []);
  const story = height > width * 1.4;
  const s = width / 1080; // scale everything from the 1080-wide design
  const cardW = 920 * s;
  const pad = 56 * s;
  const txt: React.CSSProperties = {fontFamily: font, fontWeight: 900, direction: 'rtl', textAlign: 'center'};
  return (
    <AbsoluteFill style={{backgroundColor: '#111'}} dir="rtl" lang="he">
      <Img
        src={staticFile(p.background)}
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover'}}
      />
      {/* white wall is the hero: keep it visible, darken only the lower part */}
      <AbsoluteFill
        style={{
          background: 'linear-gradient(180deg, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.25) 35%, rgba(0,0,0,0.78) 100%)',
        }}
      />
      {/* logo */}
      <div
        style={{
          position: 'absolute',
          top: (story ? 120 : 64) * s,
          left: '50%',
          width: 230 * s,
          height: 230 * s,
          borderRadius: '50%',
          overflow: 'hidden',
          transform: 'translateX(-50%)',
          border: `${6 * s}px solid rgba(255,255,255,0.9)`,
          boxShadow: '0 16px 40px rgba(0,0,0,0.45)',
          backgroundColor: '#fff',
        }}
      >
        <Img
          src={staticFile(p.logo)}
          style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
        />
      </div>
      {/* card */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          bottom: (story ? 150 : 60) * s,
          width: cardW,
          transform: 'translateX(-50%)',
          backgroundColor: 'rgba(12,12,12,0.86)',
          borderRadius: 40 * s,
          padding: `${pad}px ${pad}px ${pad * 0.8}px`,
          boxSizing: 'border-box',
          boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
          border: `${3 * s}px dashed rgba(255,230,0,0.9)`,
        }}
      >
        <div style={{...txt, fontSize: 44 * s, color: '#fff', letterSpacing: '0.08em', opacity: 0.9}}>{p.eyebrow}</div>
        <div style={{...txt, fontSize: 150 * s, color: YELLOW, lineHeight: 1.05, marginTop: 10 * s}}>{p.benefit}</div>
        <div style={{...txt, fontSize: 56 * s, color: '#fff', marginTop: 10 * s, lineHeight: 1.2}}>{p.benefitSub}</div>
        <div
          style={{
            height: 2 * s,
            backgroundColor: 'rgba(255,255,255,0.25)',
            margin: `${34 * s}px ${20 * s}px ${26 * s}px`,
          }}
        />
        {p.terms.map((t) => (
          <div key={t} style={{...txt, fontSize: 32 * s, color: 'rgba(255,255,255,0.85)', lineHeight: 1.5, fontWeight: 900}}>
            {t}
          </div>
        ))}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 30 * s,
            direction: 'rtl',
          }}
        >
          <div style={{...txt, fontSize: 36 * s, color: '#fff', textAlign: 'right'}}>
            קוד: <span style={{color: YELLOW}}>{p.code}</span>
          </div>
          <div style={{...txt, fontSize: 36 * s, color: '#fff', textAlign: 'left'}}>
            בתוקף עד <span dir="ltr">{p.validUntil}</span>
          </div>
        </div>
        <div
          style={{
            marginTop: 30 * s,
            backgroundColor: YELLOW,
            color: '#111',
            borderRadius: 24 * s,
            padding: `${16 * s}px ${24 * s}px`,
            ...txt,
            fontSize: 54 * s,
          }}
        >
          {p.contactName} · <span dir="ltr">{p.phone}</span>
        </div>
        <div style={{...txt, fontSize: 28 * s, color: 'rgba(255,255,255,0.7)', marginTop: 22 * s}}>{p.brand}</div>
      </div>
    </AbsoluteFill>
  );
};
