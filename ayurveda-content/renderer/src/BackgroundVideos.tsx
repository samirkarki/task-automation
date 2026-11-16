import React from "react";
import { Img, interpolate, Loop, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

export interface VideoSceneItem {
  clip: string;
  startFrame: number;
  durationFrames: number;
}

interface BackgroundVideosProps {
  clips: string[];
  scenes?: VideoSceneItem[];
}

export const BackgroundVideos: React.FC<BackgroundVideosProps> = ({ clips = [], scenes = [] }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Filter out any empty strings or undefined entries
  const validClips = (clips || []).filter(
    (c) => Boolean(c) && typeof c === "string" && c.trim() !== ""
  );

  const hasScenes = scenes && scenes.length > 0;

  // If no clips and no scenes are downloaded or available, render an organic ambient Ayurvedic gradient
  if (!hasScenes && validClips.length === 0) {
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

  const framesPerClip = validClips.length > 0 ? Math.ceil(durationInFrames / validClips.length) : durationInFrames;

  // Build items array: prefer explicit frame-synced scenes, fallback to equal-length clips
  const renderItems = hasScenes
    ? scenes.map((s, idx) => ({
        key: `scene-${s.clip}-${idx}`,
        clipSrc: s.clip,
        fromFrame: s.startFrame,
        duration: s.durationFrames,
      }))
    : validClips.map((clipSrc, idx) => ({
        key: `clip-${clipSrc}-${idx}`,
        clipSrc,
        fromFrame: idx * framesPerClip,
        duration: framesPerClip,
      }));

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
      {renderItems.map((item, idx) => {
        const { clipSrc, fromFrame, duration } = item;
        const resolvedSrc =
          clipSrc.startsWith("http") || clipSrc.startsWith("data:")
            ? clipSrc
            : staticFile(clipSrc);
        const isVideo = /\.(mp4|webm|mov)(\?|$)/i.test(clipSrc);

        return (
          <Sequence
            key={item.key}
            from={fromFrame}
            durationInFrames={duration}
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
                <Loop durationInFrames={60}>
                  <OffthreadVideo
                    src={resolvedSrc}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      filter: "brightness(1.02) contrast(1.02)",
                    }}
                  />
                </Loop>
              ) : (
                <Img
                  src={resolvedSrc}
                  style={{
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    filter: "brightness(1.02) contrast(1.02)",
                    transform: `scale(${interpolate(
                      frame - fromFrame,
                      [0, Math.max(1, duration)],
                      [1.0, 1.14],
                      { extrapolateRight: "clamp" }
                    )}) translate(${interpolate(
                      frame - fromFrame,
                      [0, Math.max(1, duration)],
                      [0, idx % 2 === 0 ? 12 : -12]
                    )}px, ${interpolate(
                      frame - fromFrame,
                      [0, Math.max(1, duration)],
                      [0, -8]
                    )}px)`,
                  }}
                />
              )}
            </div>
          </Sequence>
        );
      })}

      {/* Subtle bottom shadow exclusively behind lower captions for crisp text legibility without dimming the video */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "100%",
          height: "25%",
          background:
            "linear-gradient(to top, rgba(0, 0, 0, 0.45) 0%, transparent 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
};
