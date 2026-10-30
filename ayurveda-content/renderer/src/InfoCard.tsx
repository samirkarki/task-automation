import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface InfoCardData {
  type: "warning" | "remedy" | "fact";
  title: string;
  subtitle: string;
  startFrame: number;
  durationFrames: number;
}

export const InfoCard: React.FC<{ card?: InfoCardData }> = ({ card }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!card) return null;

  const { startFrame, durationFrames, type, title, subtitle } = card;

  // Only render during the active window
  if (frame < startFrame || frame > startFrame + durationFrames) {
    return null;
  }

  const relativeFrame = frame - startFrame;

  // Spring entrance & exit
  const enterSpring = spring({
    frame: relativeFrame,
    fps,
    config: { damping: 14, mass: 0.6, stiffness: 160 },
  });

  const exitProgress = interpolate(
    relativeFrame,
    [durationFrames - 15, durationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const opacity = interpolate(enterSpring, [0, 1], [0, 1]) * (1 - exitProgress);
  const translateY = interpolate(enterSpring, [0, 1], [40, 0]) - exitProgress * 30;
  const scale = interpolate(enterSpring, [0, 1], [0.92, 1.0]);

  const isWarning = type === "warning";
  const accentColor = isWarning ? "#EF4444" : "#10B981";
  const glowColor = isWarning ? "rgba(239, 68, 68, 0.4)" : "rgba(16, 185, 129, 0.4)";
  const icon = isWarning ? "⚠️" : "🌿";
  const tagText = isWarning ? "AYURVEDIC WARNING" : "THE ANCIENT FIX";

  return (
    <div
      style={{
        position: "absolute",
        top: 280,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 48px",
        zIndex: 55,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "960px",
          background: "linear-gradient(135deg, rgba(15, 23, 42, 0.88) 0%, rgba(3, 7, 18, 0.94) 100%)",
          backdropFilter: "blur(20px)",
          border: `2px solid ${accentColor}55`,
          borderRadius: "28px",
          padding: "32px 38px",
          boxShadow: `0 24px 60px rgba(0, 0, 0, 0.75), 0 0 30px ${glowColor}`,
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
      >
        {/* Header Tag */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "28px" }}>{icon}</span>
          <span
            style={{
              fontSize: "22px",
              fontWeight: 900,
              letterSpacing: "2.5px",
              color: accentColor,
              textTransform: "uppercase",
            }}
          >
            {tagText}
          </span>
        </div>

        {/* Title */}
        <div
          style={{
            fontFamily: "system-ui, -apple-system, sans-serif",
            fontSize: "42px",
            fontWeight: 800,
            color: "#FFFFFF",
            lineHeight: 1.25,
            letterSpacing: "-0.5px",
          }}
        >
          {title}
        </div>

        {/* Subtitle / Explainer */}
        {subtitle && (
          <div
            style={{
              fontFamily: "system-ui, -apple-system, sans-serif",
              fontSize: "28px",
              fontWeight: 500,
              color: "#94A3B8",
              lineHeight: 1.4,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </div>
  );
};
