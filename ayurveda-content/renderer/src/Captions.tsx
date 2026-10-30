import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface WordData {
  word: string;
  start: number; // seconds
  end: number;   // seconds
}

interface CaptionsProps {
  words: WordData[];
}

export const Captions: React.FC<CaptionsProps> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  if (!words || words.length === 0) {
    return null;
  }

  // Find index of the currently active word
  let activeIndex = -1;
  for (let i = 0; i < words.length; i++) {
    if (currentTime >= words[i].start && currentTime <= words[i].end) {
      activeIndex = i;
      break;
    }
  }

  // If between words, keep the closest recent word active for smooth visuals
  if (activeIndex === -1) {
    for (let i = words.length - 1; i >= 0; i--) {
      if (currentTime >= words[i].end) {
        activeIndex = i;
        break;
      }
    }
  }

  if (activeIndex === -1) {
    activeIndex = 0;
  }

  // Display a 3-word sliding window (previous, current, next) for maximum punchiness
  const windowSize = 3;
  const windowStart = Math.max(0, Math.min(activeIndex - 1, words.length - windowSize));
  const visibleWords = words.slice(windowStart, windowStart + windowSize);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 380,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 40px",
        zIndex: 50,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          gap: "24px",
          background: "rgba(10, 15, 22, 0.82)",
          backdropFilter: "blur(16px)",
          padding: "20px 38px",
          borderRadius: "28px",
          border: "2px solid rgba(255, 255, 255, 0.18)",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.75), 0 0 30px rgba(0, 0, 0, 0.5)",
          maxWidth: "960px",
        }}
      >
        {visibleWords.map((item, index) => {
          const globalIdx = windowStart + index;
          const isActive = globalIdx === activeIndex;

          const wordSpring = spring({
            frame: frame - Math.floor(item.start * fps),
            fps,
            config: {
              damping: 12,
              mass: 0.5,
              stiffness: 180,
            },
          });

          const scale = isActive ? interpolate(wordSpring, [0, 1], [1, 1.12]) : 1.0;

          return (
            <span
              key={`${item.word}-${globalIdx}`}
              style={{
                fontFamily: "system-ui, -apple-system, sans-serif",
                fontSize: "52px",
                fontWeight: 900,
                textTransform: "uppercase",
                letterSpacing: "2px",
                color: isActive ? "#FACC15" : "rgba(255, 255, 255, 0.88)",
                transform: `scale(${scale})`,
                transformOrigin: "center center",
                display: "inline-block",
                margin: "0 10px",
                whiteSpace: "nowrap",
                transition: "color 0.1s ease",
                textShadow: isActive
                  ? "0 0 20px rgba(250, 204, 21, 0.8), 0 4px 14px rgba(0, 0, 0, 0.95)"
                  : "0 4px 14px rgba(0, 0, 0, 0.95)",
              }}
            >
              {item.word.trim()}
            </span>
          );
        })}
      </div>
    </div>
  );
};
