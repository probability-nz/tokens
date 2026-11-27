import { useEffect, useState } from 'react';
import { createContactShadow, DiceScene } from './DiceScene';
import { createPawnResources } from './Pawn';
import { createDieResources, type Die } from '../../generators/dice/render-die';
import { kinds } from '../../generators/dice/shapes';

type Resources = {
  dice: Die[];
  pawn: ReturnType<typeof createPawnResources>;
  shadow: ReturnType<typeof createContactShadow>;
};

export function DicePreview({ animate = true }: { animate?: boolean }) {
  const [resources, setResources] = useState<Resources>();
  const [error, setError] = useState<Error>();
  useEffect(() => {
    const font = new FontFace(
      'Comfortaa',
      'url(' +
        new URL(
          '../../assets/fonts/comfortaa/Comfortaa[wght].ttf',
          import.meta.url,
        ).href +
        ')',
      { weight: '300 700' },
    );
    const dice: Die[] = [];
    let pawn: Resources['pawn'] | undefined;
    let shadow: Resources['shadow'] | undefined;
    let mounted = true;
    function release() {
      dice.splice(0).forEach((die) => die.dispose());
      pawn?.geometry.dispose();
      pawn = undefined;
      shadow?.map?.dispose();
      shadow?.dispose();
      shadow = undefined;
      document.fonts.delete(font);
    }
    font
      .load()
      .then(() => {
        if (!mounted) return;
        document.fonts.add(font);
        for (const kind of kinds) dice.push(createDieResources(kind));
        pawn = createPawnResources();
        shadow = createContactShadow();
        setResources({ dice, pawn, shadow });
      })
      .catch((reason) => {
        release();
        if (mounted)
          setError(
            reason instanceof Error ? reason : new Error(String(reason)),
          );
      });
    return () => {
      mounted = false;
      release();
    };
  }, []);
  if (error) throw error;
  return resources ? <DiceScene {...resources} animate={animate} /> : null;
}
