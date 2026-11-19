import React from 'react';
import {Composition, Still} from 'remotion';
import {Cover} from './Cover';
import {OUTRO_FRAMES, ViralReel} from './ViralReel';
import data from './data.json';
import carSeat from './data_car_seat.json';
import seat2 from './data_seat2.json';

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
        id="Seat2"
        component={ViralReel}
        durationInFrames={seat2.durationInFrames + seat2.outroFrames}
        fps={seat2.fps}
        width={seat2.width}
        height={seat2.height}
        defaultProps={{data: seat2}}
      />
      <Still
        id="Seat2Cover"
        component={Cover}
        width={1080}
        height={1920}
        defaultProps={{
          bg: 'seat2_cover_bg.png',
          logo: 'logo_sayeret.png',
          line1: 'יושבים על',
          line2: 'הלכלוך הזה?',
          badge: 'תראו מה יצא מהמושב',
        }}
      />
    </>
  );
};
