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

  const isSingleContinuous =
    renderItems.length === 1 &&
    renderItems[0].duration >= durationInFrames - 45;

  // Broadcast-quality crossfade duration in frames (18 frames = 0.6 seconds at 30fps)
  const CROSSFADE_FRAMES = 18;

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

        // Keep outgoing scene mounted during crossfade so incoming scene dissolves ON TOP of it (ZERO black gap)
        const isLast = idx === renderItems.length - 1;
        const extendedDuration = isSingleContinuous
          ? duration
          : duration + (isLast ? 0 : CROSSFADE_FRAMES);

        // Incoming scene dissolves in smoothly over CROSSFADE_FRAMES
        const localFrame = frame - fromFrame;
        const crossfadeOpacity =
          !isSingleContinuous && idx > 0
            ? interpolate(localFrame, [0, CROSSFADE_FRAMES], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              })
            : 1;

        // Cinematic cubic ease-in-out progress for organic documentary camera movement
        const rawProgress = Math.min(1.0, Math.max(0.0, localFrame / Math.max(1, duration)));
        const easedProgress =
          rawProgress < 0.5
            ? 2 * rawProgress * rawProgress
            : 1 - Math.pow(-2 * rawProgress + 2, 2) / 2;

        const kenBurnsScale = interpolate(easedProgress, [0, 1], [1.0, 1.07]);
        const kenBurnsX = interpolate(easedProgress, [0, 1], [0, idx % 2 === 0 ? 8 : -8]);
        const kenBurnsY = interpolate(easedProgress, [0, 1], [0, -5]);

        return (
          <Sequence
            key={item.key}
            from={fromFrame}
            durationInFrames={extendedDuration}
          >
            <div
              style={{
                width: "100%",
                height: "100%",
                position: "absolute",
                top: 0,
                left: 0,
                zIndex: idx + 1,
                opacity: crossfadeOpacity,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: "100%",
                  height: "100%",
                  position: "relative",
                  transform: `scale(${kenBurnsScale}) translate(${kenBurnsX}px, ${kenBurnsY}px)`,
                  transformOrigin: "center center",
                }}
              >
                {isVideo ? (
                  isSingleContinuous ? (
                    // Continuous master background: plays straight through without looping
                    <OffthreadVideo
                      src={resolvedSrc}
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        filter: "brightness(1.02) contrast(1.02)",
                      }}
                    />
                  ) : (
                    // Multi-clip: Loop seamlessly if speech segment exceeds clip length (120 frames)
                    <Loop durationInFrames={Math.min(120, duration)}>
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
                  )
                ) : (
                  <Img
                    src={resolvedSrc}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      filter: "brightness(1.02) contrast(1.02)",
                    }}
                  />
                )}
              </div>
            </div>
          </Sequence>
        );
      })}

      {/* Cinematic 35mm film vignette & warm Kodak 2383 grading pass */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          background: "radial-gradient(circle at 50% 50%, transparent 58%, rgba(0, 0, 0, 0.40) 100%)",
          pointerEvents: "none",
          zIndex: 98,
        }}
      />

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
          zIndex: 99,
        }}
      />
    </div>
  );
};
