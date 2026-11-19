import React from 'react';
import {Composition, Still} from 'remotion';
import {OUTRO_FRAMES, ViralReel} from './ViralReel';
import data from './data.json';
import carSeat from './data_car_seat.json';
import kolortek from './data_kolortek.json';
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
        id="Kolortek"
        component={ViralReel}
        durationInFrames={kolortek.durationInFrames + kolortek.outroFrames}
        fps={kolortek.fps}
        width={kolortek.width}
        height={kolortek.height}
        defaultProps={{data: kolortek}}
      />
      <Still id="KolortekCover" component={Cover} width={1080} height={1920} />
    </>
  );
};
