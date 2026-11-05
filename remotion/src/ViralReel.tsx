import React, {useEffect} from 'react';
import {
  AbsoluteFill,
  Easing,
  OffthreadVideo,
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

export const ViralReel: React.FC<{data: ReelData}> = ({data}) => {
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  useEffect(() => {
    loadHeebo();
  }, []);
  const scale = useCameraScale(frame, data.beats, fps);

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`, transformOrigin: '50% 45%'}}>
        <OffthreadVideo src={staticFile('clean.mp4')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
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
    </AbsoluteFill>
  );
};
