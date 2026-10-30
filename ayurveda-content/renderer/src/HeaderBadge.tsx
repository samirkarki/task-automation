import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";

interface HeaderBadgeProps {
  badgeText?: string;
  topicTitle?: string;
}

export const HeaderBadge: React.FC<HeaderBadgeProps> = ({
  badgeText = "AYURVEDA SECRETS",
  topicTitle,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const progress = interpolate(frame, [0, durationInFrames], [0, 100], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 60,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      {/* Top glowing progress bar */}
      <div
        style={{
          width: "100%",
          height: "8px",
          backgroundColor: "rgba(255, 255, 255, 0.15)",
        }}
      >
        <div
          style={{
            width: `${progress}%`,
            height: "100%",
            background: "linear-gradient(90deg, #10B981 0%, #FBBF24 100%)",
            boxShadow: "0 0 16px rgba(251, 191, 36, 0.8)",
          }}
        />
      </div>

      {/* Floating Category Badge */}
      <div
        style={{
          marginTop: "60px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px",
          padding: "0 40px",
          textAlign: "center",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "10px",
            background: "rgba(16, 185, 129, 0.2)",
            border: "2px solid rgba(52, 211, 153, 0.6)",
            backdropFilter: "blur(10px)",
            padding: "10px 24px",
            borderRadius: "9999px",
            color: "#34D399",
            fontSize: "26px",
            fontWeight: 800,
            letterSpacing: "2px",
            textTransform: "uppercase",
            boxShadow: "0 8px 24px rgba(16, 185, 129, 0.3)",
          }}
        >
          <span>🌿</span>
          <span>{badgeText}</span>
        </div>

        {topicTitle && (
          <div
            style={{
              color: "#F8FAFC",
              fontSize: "36px",
              fontWeight: 800,
              maxWidth: "920px",
              lineHeight: 1.25,
              textShadow: "0 4px 16px rgba(0, 0, 0, 0.8)",
            }}
          >
            {topicTitle}
          </div>
        )}
      </div>
    </div>
  );
};
