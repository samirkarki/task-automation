import React from "react";
import { Audio, CalculateMetadataFunction, Composition } from "remotion";
import { Captions, WordData } from "./Captions";
import { BackgroundVideos } from "./BackgroundVideos";
import { HeaderBadge } from "./HeaderBadge";
import { InfoCard, InfoCardData } from "./InfoCard";

export interface AyurvedaShortProps {
  audioSrc?: string;
  words?: WordData[];
  videoClips?: string[];
  badgeText?: string;
  topicTitle?: string;
  cards?: InfoCardData[];
  durationInSeconds?: number;
}

const defaultProps: AyurvedaShortProps = {
  audioSrc: "",
  words: [
    { word: "Stop", start: 0.1, end: 0.5 },
    { word: "Drinking", start: 0.5, end: 1.0 },
    { word: "Cold", start: 1.0, end: 1.4 },
    { word: "Water", start: 1.4, end: 1.9 },
    { word: "With", start: 1.9, end: 2.2 },
    { word: "Meals", start: 2.2, end: 2.8 },
  ],
  videoClips: [],
  badgeText: "GUT HEALTH SECRETS",
  topicTitle: "Extinguishing Your Digestive Fire",
  cards: [
    {
      type: "warning",
      title: "Cold Water Freezes Agni (Gut Fire)",
      subtitle: "Solidifies fats and produces toxic metabolic waste (Ama).",
      startFrame: 45,
      durationFrames: 135,
    },
    {
      type: "remedy",
      title: "The Ancient Fix: Warm Water + Fennel",
      subtitle: "Stimulates gastric enzymes and eliminates bloating in 10 minutes.",
      startFrame: 195,
      durationFrames: 150,
    },
  ],
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
  cards = [],
}) => {
  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        backgroundColor: "#030712",
        overflow: "hidden",
      }}
    >
      {/* 1. Cinematic Background Montage or Ambient Motion Canvas */}
      <BackgroundVideos clips={videoClips} />

      {/* 2. Top Category Badge & Glowing Progress Indicator */}
      <HeaderBadge badgeText={badgeText} topicTitle={topicTitle} />

      {/* 3. Educational Infographic Cards (Warnings & Remedies) */}
      {cards.map((card, i) => (
        <InfoCard key={`${card.title}-${i}`} card={card} />
      ))}

      {/* 4. High-Retention Bouncy Word Captions */}
      <Captions words={words} />

      {/* 5. Master Voiceover Audio */}
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
