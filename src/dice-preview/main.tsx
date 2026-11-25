import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { DicePreview } from './DicePreview';
function Preview() {
  const [animate, setAnimate] = useState(true);
  return (
    <>
      <label className="animation-control">
        <input
          id="animate"
          type="checkbox"
          checked={animate}
          onChange={(event) => setAnimate(event.currentTarget.checked)}
        />
        Animate
      </label>
      <DicePreview animate={animate} />
    </>
  );
}

const app = createRoot(document.getElementById('dice')!);
app.render(<Preview />);
if (import.meta.hot) import.meta.hot.dispose(() => app.unmount());
