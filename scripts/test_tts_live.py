"""Live TTS test — speaks sample commentary through Cartesia with audio processing.

Usage:
    uv run python scripts/test_tts_live.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


async def test_cartesia_tts() -> None:
    """Test Cartesia TTS with audio processor and emotion control."""
    from src.commentary.tts_engine import TTSEngine

    api_key = os.environ.get("CARTESIA_API_KEY", "")
    voice_id = os.environ.get("CARTESIA_VOICE_ID", "")

    if not api_key or not voice_id:
        print("CARTESIA_API_KEY and CARTESIA_VOICE_ID must be set in .env")
        return

    print(f"Voice ID: {voice_id}")
    print(f"Sample rate: 44100 Hz | Encoding: pcm_s16le | Audio processing: ON")
    print()

    engine = TTSEngine(api_key=api_key, voice_id=voice_id)

    try:
        print("Connecting to Cartesia WebSocket...")
        await engine.connect()
        print("Connected!\n")

        # Test 1: Single sarcastic sentence
        print("--- Test 1: Sarcastic commentary ---")
        sentence1 = "Oh wonderful, another team that thinks adding a blockchain to a to-do app is innovation."
        print(f"  Speaking: {sentence1}")
        await engine.speak(sentence1, context_id="test-01", emotion="sarcastic")
        print("  Done.\n")

        await asyncio.sleep(0.5)

        # Test 2: Enthusiastic praise
        print("--- Test 2: Enthusiastic commentary ---")
        sentence2 = "Now THIS is what I'm talking about. Clean architecture, live error handling, and they actually wrote tests."
        print(f"  Speaking: {sentence2}")
        await engine.speak(sentence2, context_id="test-02", emotion="excited")
        print("  Done.\n")

        await asyncio.sleep(0.5)

        # Test 3: Multi-sentence commentary with emotion map
        print("--- Test 3: Multi-sentence with emotion transitions ---")
        sentences = [
            "Let me break down what we just saw.",
            "The team started strong with a clean demo of their real-time collaboration feature.",
            "But then things got... interesting... when the database connection dropped mid-presentation.",
            "Credit where it's due though, their graceful degradation actually worked.",
        ]
        emotion_map = {
            0: "neutral",
            1: "surprised",
            2: "disappointed",
            3: "proud",
        }
        for i, s in enumerate(sentences):
            print(f"  [{emotion_map.get(i, 'sarcastic')}] {s}")
        await engine.speak_commentary(sentences, emotion_map)
        print("  Done.\n")

        print("All TTS tests passed!")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.close()
        print("Engine closed.")


async def test_fallback_chain() -> None:
    """Test the fallback TTS chain (OpenAI -> macOS say)."""
    from src.commentary.tts_fallback import FallbackChain, MacOSSayFallback, OpenAITTSFallback

    print("\n--- Test 4: Fallback chain ---")
    chain = FallbackChain([OpenAITTSFallback(), MacOSSayFallback()])
    print(f"  OpenAI available: {chain._fallbacks[0].available}")
    print(f"  macOS say available: {chain._fallbacks[1].available}")
    print(f"  Chain available: {chain.available}")

    if chain.available:
        sentence = "This is the fallback TTS speaking. If you hear this, the fallback chain works."
        print(f"  Speaking via fallback: {sentence}")
        await chain.speak(sentence)
        print("  Done.")
    else:
        print("  No fallbacks available, skipping.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Live TTS test")
    parser.add_argument("--fallback-only", action="store_true", help="Only test fallback chain")
    parser.add_argument("--skip-fallback", action="store_true", help="Skip fallback test")
    args = parser.parse_args()

    if args.fallback_only:
        asyncio.run(test_fallback_chain())
    else:
        asyncio.run(test_cartesia_tts())
        if not args.skip_fallback:
            asyncio.run(test_fallback_chain())
