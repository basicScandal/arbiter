import { useDisplayStore } from "../store/displayStore";
import { ArbiterSigil } from "./ArbiterSigil";

export function SigilBackground() {
  const activeScreen = useDisplayStore((s) => s.activeScreen);
  const sentences = useDisplayStore((s) => s.commentarySentences);
  const latestEmotion =
    sentences.length > 0
      ? sentences[sentences.length - 1].emotion
      : undefined;

  return (
    <div className="absolute inset-0 z-0 pointer-events-none flex items-center justify-center">
      <ArbiterSigil activeScreen={activeScreen} emotion={latestEmotion} />
    </div>
  );
}
