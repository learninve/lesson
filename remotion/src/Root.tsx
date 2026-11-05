import React from 'react';
import {Composition} from 'remotion';
import {OUTRO_FRAMES, ViralReel} from './ViralReel';
import data from './data.json';
import carSeat from './data_car_seat.json';

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
        durationInFrames={carSeat.durationInFrames + OUTRO_FRAMES}
        fps={carSeat.fps}
        width={carSeat.width}
        height={carSeat.height}
        defaultProps={{data: carSeat}}
      />
    </>
  );
};
