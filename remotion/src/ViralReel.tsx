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

export type ReelData = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  captionSource: string;
  chunks: Word[][];
  beats: number[];
  audioBeats: number[];
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
const useCameraScale = (frame: number, beats: number[], fps: number) => {
  if (frame < INTRO_ZOOM_FRAMES) {
    return interpolate(frame, [0, INTRO_ZOOM_FRAMES], [1, INTRO_ZOOM_TO], {
      easing: Easing.out(Easing.quad),
      extrapolateRight: 'clamp',
    });
  }
  const cuts = beats.filter((b) => b >= INTRO_ZOOM_FRAMES);
  const passed = cuts.filter((b) => b <= frame);
  if (passed.length === 0) return INTRO_ZOOM_TO; // hold the push-in until the first cut
  const punchedIn = passed.length % 2 === 1;
  const lastCut = passed[passed.length - 1];
  const settle = spring({frame: frame - lastCut, fps, config: {damping: 14, stiffness: 220, mass: 0.6}});
  const from = punchedIn ? PUNCH_ZOOM * 1.03 : 1.02; // never below 1.0 (no black borders)
  const to = punchedIn ? PUNCH_ZOOM : 1;
  return interpolate(settle, [0, 1], [from, to]);
};

const WordSpan: React.FC<{word: Word; frame: number; fps: number}> = ({word, frame, fps}) => {
  const active = frame >= word.startFrame && frame < word.endFrame;
  const highlighted = active || word.keyword;
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

const Captions: React.FC<{chunks: Word[][]; frame: number; fps: number; height: number}> = ({
  chunks,
  frame,
  fps,
  height,
}) => {
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
        <WordSpan key={`${w.startFrame}-${i}`} word={w} frame={frame} fps={fps} />
      ))}
    </div>
  );
};

/** Round Kolortek badge, top-centre (clear of the TikTok/Reels UI), springs in at the start. */
const LogoBadge: React.FC<{frame: number; fps: number; size: number; top: number}> = ({frame, fps, size, top}) => {
  const enter = spring({frame, fps, config: {damping: 12, stiffness: 160}});
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
        src={staticFile('logo.jpg')}
        style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
      />
    </div>
  );
};

/** End card: dark overlay, big logo, CTA line and phone number in brand yellow. */
const EndCard: React.FC<{fps: number; width: number; height: number}> = ({fps, width, height}) => {
  const frame = useCurrentFrame(); // local to the Sequence
  const fade = interpolate(frame, [0, 8], [0, 1], {extrapolateRight: 'clamp'});
  const logoIn = spring({frame, fps, config: {damping: 11, stiffness: 150}});
  const textIn = spring({frame: frame - 6, fps, config: {damping: 12, stiffness: 170}});
  const phoneIn = spring({frame: frame - 12, fps, config: {damping: 10, stiffness: 200}});
  const logoSize = Math.round(width * 0.46);
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
          src={staticFile('logo.jpg')}
          style={{width: '106%', height: '106%', marginLeft: '-3%', marginTop: '-3%', objectFit: 'cover'}}
        />
      </div>
      <div
        dir="rtl"
        style={{
          ...textStyle,
          position: 'absolute',
          top: height * 0.56,
          width: '100%',
          fontSize: 112,
          color: '#FFFFFF',
          transform: `translateY(${interpolate(textIn, [0, 1], [40, 0])}px)`,
          opacity: textIn,
        }}
      >
        להצעת מחיר
      </div>
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
      <div
        dir="rtl"
        style={{
          ...textStyle,
          position: 'absolute',
          top: height * 0.76,
          width: '100%',
          fontSize: 60,
          color: '#FFFFFF',
          WebkitTextStroke: '8px #000',
          opacity: interpolate(frame, [18, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
        }}
      >
        קולורטק · עבודה עברית
      </div>
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
  const scale = useCameraScale(Math.min(frame, mainFrames - 1), data.beats, fps);
  const videoStyle: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover'};

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: '50% 45%'}}>
        <Sequence from={0} durationInFrames={mainFrames} layout="none">
          <OffthreadVideo src={staticFile('clean.mp4')} style={videoStyle} />
        </Sequence>
        <Sequence from={mainFrames} durationInFrames={OUTRO_FRAMES} layout="none">
          <Freeze frame={mainFrames - 1}>
            <OffthreadVideo src={staticFile('clean.mp4')} muted style={videoStyle} />
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
      <Captions chunks={data.chunks} frame={frame} fps={fps} height={height} />
      {frame < mainFrames ? (
        <LogoBadge frame={frame} fps={fps} size={Math.round(width * 0.2)} top={Math.round(height * 0.075)} />
      ) : null}
      <Sequence from={mainFrames} durationInFrames={OUTRO_FRAMES} layout="none">
        <EndCard fps={fps} width={width} height={height} />
      </Sequence>
    </AbsoluteFill>
  );
};
