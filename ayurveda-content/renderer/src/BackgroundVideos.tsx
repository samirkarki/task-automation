import React from "react";
import { Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

interface BackgroundVideosProps {
  clips: string[];
}

export const BackgroundVideos: React.FC<BackgroundVideosProps> = ({ clips = [] }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Filter out any empty strings or undefined entries
  const validClips = (clips || []).filter(
    (c) => Boolean(c) && typeof c === "string" && c.trim() !== ""
  );

  // If no clips are downloaded or available, render an organic ambient Ayurvedic gradient
  if (validClips.length === 0) {
    const pulse = interpolate(
      Math.sin((frame / 30) * 1.5),
      [-1, 1],
      [0.85, 1.15]
    );

    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          overflow: "hidden",
          background: "radial-gradient(circle at 50% 35%, #064E3B 0%, #06281E 50%, #030D0A 100%)",
        }}
      >
        {/* Breathing Prana light orb */}
        <div
          style={{
            position: "absolute",
            top: "25%",
            left: "20%",
            width: "600px",
            height: "600px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, transparent 70%)",
            transform: `scale(${pulse})`,
            filter: "blur(60px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "20%",
            right: "15%",
            width: "500px",
            height: "500px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(245, 158, 11, 0.18) 0%, transparent 70%)",
            transform: `scale(${2.0 - pulse})`,
            filter: "blur(50px)",
          }}
        />
      </div>
    );
  }

  const framesPerClip = Math.ceil(durationInFrames / validClips.length);

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        overflow: "hidden",
        backgroundColor: "#000000",
      }}
    >
      {validClips.map((clipSrc, idx) => {
        const fromFrame = idx * framesPerClip;
        const resolvedSrc =
          clipSrc.startsWith("http") || clipSrc.startsWith("data:")
            ? clipSrc
            : staticFile(clipSrc);
        const isVideo = /\.(mp4|webm|mov)(\?|$)/i.test(clipSrc);

        return (
          <Sequence
            key={`${clipSrc}-${idx}`}
            from={fromFrame}
            durationInFrames={framesPerClip}
          >
            <div
              style={{
                width: "100%",
                height: "100%",
                position: "relative",
                overflow: "hidden",
              }}
            >
              {isVideo ? (
                <OffthreadVideo
                  src={resolvedSrc}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    filter: "brightness(0.75) contrast(1.15)",
                  }}
                />
              ) : (
                <Img
                  src={resolvedSrc}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    filter: "brightness(0.72) contrast(1.18)",
                    transform: `scale(${1.04 + (idx % 2 === 0 ? 0.08 : -0.04) * ((frame - fromFrame) / framesPerClip)})`,
                    transition: "transform 0.05s linear",
                  }}
                />
              )}
            </div>
          </Sequence>
        );
      })}

      {/* Cinematic Dark Vignette & Gradient Overlays for High Legibility */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background:
            "radial-gradient(circle at center, transparent 40%, rgba(0, 0, 0, 0.75) 100%)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "100%",
          height: "45%",
          background:
            "linear-gradient(to top, rgba(0, 0, 0, 0.85) 0%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
};
