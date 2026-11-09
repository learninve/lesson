import React from 'react';
import {Composition} from 'remotion';
import {OUTRO_FRAMES, ViralReel} from './ViralReel';
import data from './data.json';
import carSeat from './data_car_seat.json';
import board from './data_board.json';
import {Voucher, voucherDefaults} from './Voucher';

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
        id="Board"
        component={ViralReel}
        durationInFrames={board.durationInFrames + board.outroFrames}
        fps={board.fps}
        width={board.width}
        height={board.height}
        defaultProps={{data: board}}
      />
      <Composition id="VoucherStory" component={Voucher} durationInFrames={1} fps={30} width={1080} height={1920} defaultProps={voucherDefaults} />
      <Composition id="VoucherFeed" component={Voucher} durationInFrames={1} fps={30} width={1080} height={1350} defaultProps={voucherDefaults} />
    </>
  );
};
