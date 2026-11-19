import React, {useEffect} from 'react';
import {
  AbsoluteFill,
  Easing,
  Freeze,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {FONT_FAMILY, loadHeebo} from './fonts';

export type Word = {
  text: string;
  start: number;
  end: number;
  keyword: boolean;
  startFrame: number;
  endFrame: number;
};

export type Outro = {line1: string; line2: string; phone?: string; footer?: string; whatsapp?: boolean};

export type ReelData = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  captionSource: string;
  chunks: Word[][];
  beats: number[];
  audioBeats: number[];
  // optional per-video overrides (defaults reproduce the original viral_output.mp4)
  video?: string; // file in public/
  logo?: string; // file in public/
  logoRound?: boolean; // false for logos that already have their own (transparent) round shape
  introFrames?: number;
  introZoomTo?: number;
  zoomOrigin?: string;
  highlightActive?: boolean; // false: only `keyword` words turn yellow
  outro?: Outro;
  outroFrames?: number;
  result?: {before: string; after: string; endBg?: string; frames: number; beforeLabel: string; afterLabel: string};
};

const YELLOW = '#FFE600';
const INTRO_ZOOM_FRAMES = 90; // 3 s @ 30 fps: gradual 1.0 -> 1.12
const INTRO_ZOOM_TO = 1.12;
const PUNCH_ZOOM = 1.15;
const CAPTION_TOP = 0.65; // safe zone: 65 % from the top
const MAX_WORDS = 3;
export const OUTRO_FRAMES = 60; // 2 s end card: logo + "להצעת מחיר" + phone
const PHONE = '0533237036';
const PHONE_DISPLAY = '053-323-7036';

/**
 * Camera scale for a frame:
 *  - frames 0..90: slow push-in 1.0 -> 1.12 (hook)
 *  - after that every beat toggles a jump cut between 1.0 and 1.15, with a
 *    tiny spring settle so the cut feels snappy instead of static.
 */
const useCameraScale = (
  frame: number,
  beats: number[],
  fps: number,
  introFrames = INTRO_ZOOM_FRAMES,
  introZoomTo = INTRO_ZOOM_TO,
) => {
  if (frame < introFrames) {
    return interpolate(frame, [0, introFrames], [1, introZoomTo], {
      easing: Easing.out(Easing.quad),
      extrapolateRight: 'clamp',
    });
  }
  const cuts = beats.filter((b) => b >= introFrames);
  const passed = cuts.filter((b) => b <= frame);
  if (passed.length === 0) return introZoomTo; // hold the push-in until the first cut
  // if the push-in already ended at punch level, the first cut zooms OUT so it is actually visible
  const startsPunched = introZoomTo >= PUNCH_ZOOM;
  const punchedIn = startsPunched ? passed.length % 2 === 0 : passed.length % 2 === 1;
  const lastCut = passed[passed.length - 1];
  const settle = spring({frame: frame - lastCut, fps, config: {damping: 14, stiffness: 220, mass: 0.6}});
  const from = punchedIn ? PUNCH_ZOOM * 1.03 : 1.02; // never below 1.0 (no black borders)
  const to = punchedIn ? PUNCH_ZOOM : 1;
  return interpolate(settle, [0, 1], [from, to]);
};

const WordSpan: React.FC<{word: Word; frame: number; fps: number; highlightActive: boolean}> = ({
  word,
  frame,
  fps,
  highlightActive,
}) => {
  const active = frame >= word.startFrame && frame < word.endFrame;
  const highlighted = (highlightActive && active) || word.keyword;
  // Pop: springs from 1 -> ~1.18 and settles at 1.1 while the word is being said.
  const pop = spring({frame: frame - word.startFrame, fps, config: {damping: 9, stiffness: 260, mass: 0.5}});
  const scale = active ? interpolate(pop, [0, 1], [1, 1.1]) : word.keyword && frame >= word.endFrame ? 1.04 : 1;
  const fill = highlighted ? YELLOW : '#FFFFFF';
  return (
    <span
      style={{
        display: 'inline-block',
        color: fill,
        transform: `scale(${scale})`,
        transformOrigin: 'center',
        margin: '0 0.18em',
        WebkitTextStroke: '14px #000',
        paintOrder: 'stroke fill',
        textShadow: '0 10px 22px rgba(0,0,0,0.65)',
        willChange: 'transform',
      }}
    >
      {word.text}
    </span>
  );
};

const Captions: React.FC<{
  chunks: Word[][];
  frame: number;
  fps: number;
  height: number;
  highlightActive: boolean;
}> = ({chunks, frame, fps, height, highlightActive}) => {
  const chunk = chunks.find((c) => frame >= c[0].startFrame && frame < c[c.length - 1].endFrame);
  if (!chunk) return null;
  const visible = chunk.slice(0, MAX_WORDS);
  const enter = spring({frame: frame - chunk[0].startFrame, fps, config: {damping: 12, stiffness: 200}});
  const translateY = interpolate(enter, [0, 1], [26, 0]);
  const opacity = interpolate(frame - chunk[0].startFrame, [0, 3], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <div
      dir="rtl"
      lang="he"
      style={{
        position: 'absolute',
        top: height * CAPTION_TOP,
        left: 0,
        width: '100%',
        padding: '0 70px',
        boxSizing: 'border-box',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexWrap: 'nowrap',
        direction: 'rtl',
        unicodeBidi: 'isolate',
        textAlign: 'center',
        fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
        fontWeight: 900,
        fontSize: 104,
        lineHeight: 1.15,
        letterSpacing: '-0.01em',
        transform: `translateY(${translateY - 50}px)`,
        opacity,
        whiteSpace: 'nowrap',
      }}
    >
      {visible.map((w, i) => (
        <WordSpan key={`${w.startFrame}-${i}`} word={w} frame={frame} fps={fps} highlightActive={highlightActive} />
      ))}
    </div>
  );
};

/** Round Kolortek badge, top-centre (clear of the TikTok/Reels UI), springs in at the start. */
const LogoBadge: React.FC<{
  frame: number;
  fps: number;
  size: number;
  top: number;
  file: string;
  round: boolean;
}> = ({frame, fps, size, top, file, round}) => {
  const enter = spring({frame, fps, config: {damping: 12, stiffness: 160}});
  if (!round) {
    return (
      <Img
        src={staticFile(file)}
        style={{
          position: 'absolute',
          top,
          left: '50%',
          width: size,
          height: size,
          transform: `translateX(-50%) scale(${interpolate(enter, [0, 1], [0.6, 1])})`,
          opacity: enter,
          filter: 'drop-shadow(0 12px 24px rgba(0,0,0,0.5))',
        }}
      />
    );
  }
  return (
    <div
      style={{
        position: 'absolute',
        top,
        left: '50%',
        width: size,
        height: size,
        borderRadius: '50%',
        overflow: 'hidden',
        transform: `translateX(-50%) scale(${interpolate(enter, [0, 1], [0.6, 1])})`,
        opacity: enter,
        boxShadow: '0 12px 30px rgba(0,0,0,0.45)',
        border: '4px solid rgba(255,255,255,0.85)',
        backgroundColor: '#fff',
      }}
    >
      <Img
        src={staticFile(file)}
        style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
      />
    </div>
  );
};

export const WA_GREEN = '#25D366';

/** WhatsApp glyph (simple white speech bubble + handset), inline so rendering needs no network. */
export const WhatsAppIcon: React.FC<{size: number}> = ({size}) => (
  <svg width={size} height={size} viewBox="0 0 32 32" style={{flexShrink: 0}}>
    <path
      fill="#fff"
      d="M16 3C9 3 3.3 8.6 3.3 15.6c0 2.4.7 4.7 1.9 6.7L3 29l6.9-2.2c1.9 1 4 1.6 6.1 1.6 7 0 12.7-5.7 12.7-12.7S23 3 16 3zm0 23.2c-1.9 0-3.8-.5-5.4-1.5l-.4-.2-4.1 1.3 1.3-4-.3-.4c-1.1-1.7-1.7-3.7-1.7-5.7C5.4 9.8 10.1 5.1 16 5.1s10.6 4.7 10.6 10.6S21.9 26.2 16 26.2z"
    />
    <path
      fill="#fff"
      d="M21.8 18.4c-.3-.2-1.9-.9-2.2-1-.3-.1-.5-.2-.7.2-.2.3-.8 1-1 1.2-.2.2-.4.2-.7.1-.3-.2-1.4-.5-2.6-1.6-1-.9-1.6-1.9-1.8-2.2-.2-.3 0-.5.1-.7l.5-.6c.2-.2.2-.3.3-.6.1-.2 0-.4 0-.6l-1-2.4c-.3-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.8s1.2 3.2 1.4 3.5c.2.2 2.4 3.6 5.7 5 .8.3 1.4.5 1.9.7.8.3 1.5.2 2.1.1.6-.1 1.9-.8 2.2-1.5.3-.8.3-1.4.2-1.5-.1-.2-.3-.3-.6-.4z"
    />
  </svg>
);

/** End card for a WhatsApp CTA: badge, "להצעת מחיר", pulsing green WhatsApp button with the number. */
const WhatsAppCard: React.FC<{fps: number; width: number; height: number; logo: string; outro: Outro}> = ({
  fps,
  width,
  height,
  logo,
  outro,
}) => {
  const frame = useCurrentFrame();
  const fade = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const logoIn = spring({frame, fps, config: {damping: 11, stiffness: 150}});
  const l1 = spring({frame: frame - 6, fps, config: {damping: 12, stiffness: 170}});
  const l2 = spring({frame: frame - 12, fps, config: {damping: 12, stiffness: 170}});
  const btn = spring({frame: frame - 18, fps, config: {damping: 9, stiffness: 190}});
  const pulse = frame > 34 ? 1 + 0.035 * Math.sin(((frame - 34) / fps) * Math.PI * 2 * 1.4) : 1;
  const logoSize = Math.round(width * 0.42);
  const font = `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`;
  const text: React.CSSProperties = {
    position: 'absolute',
    width: '100%',
    fontFamily: font,
    fontWeight: 900,
    direction: 'rtl',
    textAlign: 'center',
    WebkitTextStroke: '12px #000',
    paintOrder: 'stroke fill',
    textShadow: '0 10px 22px rgba(0,0,0,0.65)',
    whiteSpace: 'nowrap',
  };
  return (
    <AbsoluteFill style={{opacity: fade}}>
      <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(20,28,12,0.78) 0%, rgba(30,40,18,0.9) 100%)'}} />
      <div
        style={{
          position: 'absolute',
          top: height * 0.12,
          left: '50%',
          width: logoSize,
          height: logoSize,
          borderRadius: '50%',
          overflow: 'hidden',
          transform: `translateX(-50%) scale(${interpolate(logoIn, [0, 1], [0.5, 1])})`,
          boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
          border: '8px solid rgba(255,255,255,0.9)',
          backgroundColor: '#fff',
        }}
      >
        <Img src={staticFile(logo)} style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}} />
      </div>
      <div dir="rtl" style={{...text, top: height * 0.44, fontSize: 120, color: '#fff', opacity: l1, transform: `translateY(${interpolate(l1, [0, 1], [40, 0])}px)`}}>
        {outro.line1}
      </div>
      <div dir="rtl" style={{...text, top: height * 0.52, fontSize: 104, color: YELLOW, opacity: l2, transform: `translateY(${interpolate(l2, [0, 1], [40, 0])}px)`}}>
        {outro.line2}
      </div>
      <a
        href={`https://wa.me/972${outro.phone!.replace(/\D/g, '').replace(/^0/, '')}`}
        dir="ltr"
        style={{
          position: 'absolute',
          top: height * 0.635,
          left: '50%',
          display: 'flex',
          alignItems: 'center',
          gap: 30,
          padding: '26px 56px 30px',
          borderRadius: 999,
          backgroundColor: WA_GREEN,
          border: '6px solid #fff',
          boxShadow: '0 18px 40px rgba(0,0,0,0.55)',
          color: '#fff',
          textDecoration: 'none',
          fontFamily: font,
          fontWeight: 900,
          fontSize: 104,
          lineHeight: 1,
          letterSpacing: '0.02em',
          whiteSpace: 'nowrap',
          opacity: interpolate(btn, [0, 1], [0, 1], {extrapolateRight: 'clamp'}),
          transform: `translateX(-50%) scale(${interpolate(btn, [0, 1], [0.6, 1]) * pulse})`,
        }}
      >
        <WhatsAppIcon size={112} />
        <span>{outro.phone}</span>
      </a>
      <div
        dir="rtl"
        style={{
          ...text,
          top: height * 0.8,
          fontSize: 44,
          color: '#fff',
          WebkitTextStroke: '8px #000',
          opacity: interpolate(frame, [26, 36], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        {outro.footer ?? ''}
      </div>
    </AbsoluteFill>
  );
};

/** End card: dark overlay, big logo, CTA line and phone number in brand yellow. */
const EndCard: React.FC<{
  fps: number;
  width: number;
  height: number;
  logo: string;
  logoRound: boolean;
  outro?: Outro;
}> = ({fps, width, height, logo, logoRound, outro}) => {
  const frame = useCurrentFrame(); // local to the Sequence
  const fade = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const logoIn = spring({frame, fps, config: {damping: 11, stiffness: 150}});
  const textIn = spring({frame: frame - 6, fps, config: {damping: 12, stiffness: 170}});
  const phoneIn = spring({frame: frame - 12, fps, config: {damping: 10, stiffness: 200}});
  const logoSize = Math.round(width * 0.46);
  if (outro?.whatsapp && outro.phone) {
    return <WhatsAppCard fps={fps} width={width} height={height} logo={logo} outro={outro} />;
  }
  const textStyle: React.CSSProperties = {
    fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
    fontWeight: 900,
    direction: 'rtl',
    textAlign: 'center',
    WebkitTextStroke: '12px #000',
    paintOrder: 'stroke fill',
    textShadow: '0 10px 22px rgba(0,0,0,0.65)',
    whiteSpace: 'nowrap',
  };
  return (
    <AbsoluteFill style={{opacity: fade, justifyContent: 'center', alignItems: 'center'}}>
      <AbsoluteFill style={{backgroundColor: 'rgba(20, 28, 12, 0.72)'}} />
      {logoRound ? (
        <div
          style={{
            position: 'absolute',
            top: height * 0.17,
            left: '50%',
            width: logoSize,
            height: logoSize,
            borderRadius: '50%',
            overflow: 'hidden',
            transform: `translateX(-50%) scale(${interpolate(logoIn, [0, 1], [0.5, 1])})`,
            boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
            border: '8px solid rgba(255,255,255,0.9)',
            backgroundColor: '#fff',
          }}
        >
          <Img
            src={staticFile(logo)}
            style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
          />
        </div>
      ) : (
        <Img
          src={staticFile(logo)}
          style={{
            position: 'absolute',
            top: height * 0.15,
            left: '50%',
            width: logoSize,
            height: logoSize,
            transform: `translateX(-50%) scale(${interpolate(logoIn, [0, 1], [0.5, 1])})`,
            filter: 'drop-shadow(0 20px 40px rgba(0,0,0,0.6))',
          }}
        />
      )}
      <div
        dir="rtl"
        style={{
          ...textStyle,
          position: 'absolute',
          top: height * (outro?.phone ? 0.5 : 0.56),
          width: '100%',
          fontSize: 112,
          color: '#FFFFFF',
          transform: `translateY(${interpolate(textIn, [0, 1], [40, 0])}px)`,
          opacity: textIn,
        }}
      >
        {outro ? outro.line1 : 'להצעת מחיר'}
      </div>
      {outro ? (
        <div
          dir="rtl"
          style={{
            ...textStyle,
            position: 'absolute',
            top: height * (outro.phone ? 0.575 : 0.645),
            width: '100%',
            fontSize: 132,
            color: YELLOW,
            transform: `scale(${interpolate(phoneIn, [0, 1], [0.7, 1])})`,
            opacity: phoneIn,
          }}
        >
          {outro.line2}
        </div>
      ) : (
      <a
        href={`tel:${PHONE}`}
        dir="ltr"
        style={{
          ...textStyle,
          position: 'absolute',
          top: height * 0.645,
          width: '100%',
          fontSize: 132,
          color: YELLOW,
          letterSpacing: '0.04em',
          textDecoration: 'none',
          transform: `scale(${interpolate(phoneIn, [0, 1], [0.7, 1])})`,
          opacity: phoneIn,
        }}
      >
        {PHONE_DISPLAY}
      </a>
      )}
      {outro?.phone ? (
        <a
          href={`tel:${outro.phone.replace(/\D/g, '')}`}
          dir="ltr"
          style={{
            ...textStyle,
            position: 'absolute',
            top: height * 0.665,
            width: '100%',
            fontSize: 138,
            color: '#FFFFFF',
            letterSpacing: '0.04em',
            textDecoration: 'none',
            transform: `scale(${interpolate(spring({frame: frame - 18, fps, config: {damping: 10, stiffness: 200}}), [0, 1], [0.7, 1])})`,
            opacity: interpolate(frame, [18, 24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
          }}
        >
          {outro.phone}
        </a>
      ) : null}
      <div
        dir="rtl"
        style={{
          ...textStyle,
          position: 'absolute',
          top: height * (outro?.phone ? 0.78 : 0.76),
          width: '100%',
          fontSize: 60,
          color: '#FFFFFF',
          WebkitTextStroke: '8px #000',
          opacity: interpolate(frame, [24, 34], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        {outro ? outro.footer ?? '' : 'קולורטק · עבודה עברית'}
      </div>
    </AbsoluteFill>
  );
};

/** Real before/after split from two frames of the raw footage; "after" wipes in from the right. */
const BeforeAfter: React.FC<{
  result: NonNullable<ReelData['result']>;
  fps: number;
  width: number;
  height: number;
}> = ({result, fps, width, height}) => {
  const frame = useCurrentFrame(); // local to the Sequence
  const half = height / 2;
  const push = interpolate(frame, [0, result.frames], [1, 1.07], {extrapolateRight: 'clamp'});
  const reveal = interpolate(frame, [14, 30], [100, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const pill = (bg: string, color: string, inFrame: number, text: string, top: number) => {
    const e = spring({frame: frame - inFrame, fps, config: {damping: 11, stiffness: 200}});
    return (
      <div
        dir="rtl"
        style={{
          position: 'absolute',
          top,
          right: 44,
          padding: '4px 40px 10px',
          borderRadius: 24,
          backgroundColor: bg,
          color,
          fontFamily: `${FONT_FAMILY}, 'Rubik', 'Arial Hebrew', sans-serif`,
          fontWeight: 900,
          fontSize: 92,
          lineHeight: 1.2,
          boxShadow: '0 10px 26px rgba(0,0,0,0.5)',
          transform: `scale(${interpolate(e, [0, 1], [0.6, 1])})`,
          opacity: e,
        }}
      >
        {text}
      </div>
    );
  };
  const imgStyle: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${push})`};
  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <div style={{position: 'absolute', top: 0, left: 0, width, height: half, overflow: 'hidden'}}>
        <Img src={staticFile(result.before)} style={imgStyle} />
      </div>
      <div
        style={{
          position: 'absolute',
          top: half,
          left: 0,
          width,
          height: half,
          overflow: 'hidden',
          transform: `translateX(${reveal}%)`,
        }}
      >
        <Img src={staticFile(result.after)} style={imgStyle} />
      </div>
      <div style={{position: 'absolute', top: half - 4, left: 0, width, height: 8, backgroundColor: YELLOW}} />
      {pill('rgba(0,0,0,0.72)', '#FFFFFF', 4, result.beforeLabel, half - 150 - 80)}
      {pill(YELLOW, '#111111', 22, result.afterLabel, height - 150 - 80)}
    </AbsoluteFill>
  );
};

export const ViralReel: React.FC<{data: ReelData}> = ({data}) => {
  const frame = useCurrentFrame();
  const {fps, height, width} = useVideoConfig();
  useEffect(() => {
    loadHeebo();
  }, []);
  const mainFrames = data.durationInFrames;
  const scale = useCameraScale(
    Math.min(frame, mainFrames - 1),
    data.beats,
    fps,
    data.introFrames,
    data.introZoomTo,
  );
  const videoFile = data.video ?? 'clean.mp4';
  const logoFile = data.logo ?? 'logo.jpg';
  const logoRound = data.logoRound ?? true;
  const videoStyle: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover'};
  const resultFrames = data.result?.frames ?? 0;
  const outroFrames = data.outroFrames ?? OUTRO_FRAMES;
  const endFrom = mainFrames + resultFrames;

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: data.zoomOrigin ?? '50% 45%'}}>
        <Sequence from={0} durationInFrames={mainFrames} layout="none">
          <OffthreadVideo src={staticFile(videoFile)} style={videoStyle} />
        </Sequence>
        <Sequence from={mainFrames} durationInFrames={resultFrames + outroFrames} layout="none">
          <Freeze frame={mainFrames - 1}>
            <OffthreadVideo src={staticFile(videoFile)} muted style={videoStyle} />
          </Freeze>
        </Sequence>
      </AbsoluteFill>
      {/* subtle vignette so white text stays readable on the bright ceiling */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse at 50% 60%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.35) 100%)',
          pointerEvents: 'none',
        }}
      />
      <Captions
        chunks={data.chunks}
        frame={frame}
        fps={fps}
        height={height}
        highlightActive={data.highlightActive ?? true}
      />
      {frame < mainFrames ? (
        <LogoBadge
          frame={frame}
          fps={fps}
          size={Math.round(width * 0.2)}
          top={Math.round(height * 0.075)}
          file={logoFile}
          round={logoRound}
        />
      ) : null}
      {data.result ? (
        <Sequence from={mainFrames} durationInFrames={resultFrames} layout="none">
          <BeforeAfter result={data.result} fps={fps} width={width} height={height} />
        </Sequence>
      ) : null}
      {data.result && frame >= mainFrames && frame < endFrom ? (
        <LogoBadge
          frame={999}
          fps={fps}
          size={Math.round(width * 0.2)}
          top={Math.round(height * 0.075)}
          file={logoFile}
          round={logoRound}
        />
      ) : null}
      <Sequence from={endFrom} durationInFrames={outroFrames} layout="none">
        {data.result?.endBg ? (
          <Img src={staticFile(data.result.endBg)} style={{...videoStyle, position: 'absolute', top: 0, left: 0}} />
        ) : null}
        <EndCard fps={fps} width={width} height={height} logo={logoFile} logoRound={logoRound} outro={data.outro} />
      </Sequence>
    </AbsoluteFill>
  );
};
