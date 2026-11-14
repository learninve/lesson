import React from 'react';
import {Composition, Still} from 'remotion';
import {OUTRO_FRAMES, ViralReel} from './ViralReel';
import data from './data.json';
import carSeat from './data_car_seat.json';
import shpachtel from './data_shpachtel.json';
import {Cover} from './Cover';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ViralReel"
        component={ViralReel}
        durationInFrames={data.durationInFrames + OUTRO_FRAMES}
        fps={data.fps}
        width={data.width}
        height={data.height}
        defaultProps={{data}}
      />
      <Composition
        id="CarSeat"
        component={ViralReel}
        durationInFrames={carSeat.durationInFrames + carSeat.result.frames + carSeat.outroFrames}
        fps={carSeat.fps}
        width={carSeat.width}
        height={carSeat.height}
        defaultProps={{data: carSeat}}
      />
      <Composition
        id="Shpachtel"
        component={ViralReel}
        durationInFrames={shpachtel.durationInFrames + shpachtel.outroFrames}
        fps={shpachtel.fps}
        width={shpachtel.width}
        height={shpachtel.height}
        defaultProps={{data: shpachtel}}
      />
      <Still
        id="ShpachtelCover"
        component={Cover}
        width={1080}
        height={1920}
        defaultProps={{
          bg: 'shpachtel_cover_bg.png',
          logo: 'logo.jpg',
          line1: 'קיר חלק',
          line2: 'כמו מראה',
          tag: 'להצעת מחיר',
          phone: '053-323-7036',
        }}
      />
    </>
  );
};
