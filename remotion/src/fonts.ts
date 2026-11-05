import {continueRender, delayRender, staticFile} from 'remotion';

// Heebo 900 (Google Fonts), served from public/fonts so rendering needs no network.
export const FONT_FAMILY = 'Heebo';
let loaded: Promise<void> | null = null;

export const loadHeebo = (): Promise<void> => {
  if (loaded) return loaded;
  const handle = delayRender('Loading Heebo 900');
  const face = new FontFace(FONT_FAMILY, `url(${staticFile('fonts/Heebo-900.ttf')}) format('truetype')`, {
    weight: '900',
    style: 'normal',
  });
  loaded = face
    .load()
    .then((f) => {
      document.fonts.add(f);
      continueRender(handle);
    })
    .catch((err) => {
      console.error('Heebo failed to load', err);
      continueRender(handle);
    });
  return loaded;
};
