import React from "react";
import { Audio, CalculateMetadataFunction, Composition, staticFile } from "remotion";
import { Captions, WordData } from "./Captions";
import { BackgroundVideos } from "./BackgroundVideos";
import { HeaderBadge } from "./HeaderBadge";

export interface AyurvedaShortProps {
  audioSrc?: string;
  words?: WordData[];
  videoClips?: string[];
  badgeText?: string;
  topicTitle?: string;
  durationInSeconds?: number;
}

const defaultProps: AyurvedaShortProps = {
  audioSrc: "",
  words: [
    { word: "Ancient", start: 0.1, end: 0.6 },
    { word: "Ayurvedic", start: 0.6, end: 1.2 },
    { word: "Secrets", start: 1.2, end: 1.8 },
    { word: "For", start: 1.8, end: 2.1 },
    { word: "Daily", start: 2.1, end: 2.5 },
    { word: "Life", start: 2.5, end: 3.0 },
  ],
  videoClips: [],
  badgeText: "AYURVEDA SECRETS",
  topicTitle: "Morning Gut Reset",
  durationInSeconds: 30,
};

const calculateMetadata: CalculateMetadataFunction<AyurvedaShortProps> = ({
  props,
}) => {
  const fps = 30;
  const durationSec = props.durationInSeconds || 30;
  return {
    durationInFrames: Math.ceil(durationSec * fps),
    fps,
    width: 1080,
    height: 1920,
  };
};

export const AyurvedaShort: React.FC<AyurvedaShortProps> = ({
  audioSrc,
  words = [],
  videoClips = [],
  badgeText = "AYURVEDA SECRETS",
  topicTitle,
}) => {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        backgroundColor: "#000000",
        overflow: "hidden",
      }}
    >
      {/* 1. Background Video Montage */}
      <BackgroundVideos clips={videoClips} />

      {/* 2. Top Header and Glowing Progress Indicator */}
      <HeaderBadge badgeText={badgeText} topicTitle={topicTitle} />

      {/* 3. TikTok Bouncy Captions */}
      <Captions words={words} />

      {/* 4. Master Audio Track */}
      {audioSrc ? <Audio src={audioSrc} /> : null}
    </div>
  );
};

export const MyComposition = () => {
  return (
    <Composition
      id="AyurvedaShort"
      component={AyurvedaShort}
      durationInFrames={30 * 30}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
