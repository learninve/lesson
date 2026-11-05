import React from 'react';
import {Composition} from 'remotion';
import {ViralReel} from './ViralReel';
import data from './data.json';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ViralReel"
      component={ViralReel}
      durationInFrames={data.durationInFrames}
      fps={data.fps}
      width={data.width}
      height={data.height}
      defaultProps={{data}}
    />
  );
};
