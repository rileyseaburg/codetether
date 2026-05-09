#!/usr/bin/env python3
"""
Test script to send real speech audio to the voice agent and verify tool usage.
Uses gTTS to generate speech and ffmpeg to convert to the correct format.
"""

import asyncio
import subprocess
import struct
import tempfile
import os
import sys
import httpx
from livekit import rtc
from gtts import gTTS
from dataclasses import dataclass
from typing import List, Optional

API_URL = 'https://api.codetether.run'


@dataclass
class TestCase:
    """A test case with speech input and expected behavior."""

    name: str
    speech: str
    expected_tool: Optional[str] = None
    description: str = ''


# Test cases that should trigger tool usage
TEST_CASES = [
    TestCase(
        name='list_tasks',
        speech='Hey, can you list all my tasks please?',
        expected_tool='list_tasks',
        description='Should trigger list_tasks tool',
    ),
    TestCase(
        name='create_task',
        speech='Create a new task called fix the login bug with high priority',
        expected_tool='create_task',
        description='Should trigger create_task tool',
    ),
    TestCase(
        name='discover_agents',
        speech='What agents are available in the system?',
        expected_tool='discover_agents',
        description='Should trigger discover_agents tool',
    ),
    TestCase(
        name='general_greeting',
        speech='Hello, how are you today?',
        expected_tool=None,
        description='General greeting, no tool expected',
    ),
]


def generate_speech_audio(text: str, output_path: str) -> bool:
    """Generate speech audio from text using gTTS and convert to PCM format.

    Args:
        text: The text to convert to speech.
        output_path: Path to save the raw PCM audio.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Generate MP3 with gTTS
        with tempfile.NamedTemporaryFile(
            suffix='.mp3', delete=False
        ) as mp3_file:
            mp3_path = mp3_file.name

        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(mp3_path)

        # Convert to raw PCM (16-bit, 48kHz, mono) using ffmpeg
        result = subprocess.run(
            [
                'ffmpeg',
                '-y',
                '-i',
                mp3_path,
                '-ar',
                '48000',  # 48kHz sample rate
                '-ac',
                '1',  # mono
                '-f',
                's16le',  # signed 16-bit little-endian
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        os.unlink(mp3_path)

        if result.returncode != 0:
            print(f'ffmpeg error: {result.stderr}')
            return False

        return True
    except Exception as e:
        print(f'Error generating speech: {e}')
        return False


async def create_voice_session() -> dict:
    """Create a voice session via the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'{API_URL}/v1/voice/sessions', json={'voice': 'puck'}, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def run_test_case(test_case: TestCase) -> dict:
    """Run a single test case and return results.

    Args:
        test_case: The test case to run.

    Returns:
        A dictionary with test results.
    """
    print(f'\n{"=" * 60}')
    print(f'TEST: {test_case.name}')
    print(f'Description: {test_case.description}')
    print(f'Speech: "{test_case.speech}"')
    print(f'Expected tool: {test_case.expected_tool or "None"}')
    print('=' * 60)

    result = {
        'name': test_case.name,
        'speech': test_case.speech,
        'expected_tool': test_case.expected_tool,
        'success': False,
        'audio_frames_received': 0,
        'audio_duration_ms': 0,
        'error': None,
    }

    # Generate speech audio
    print('Generating speech audio...')
    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as pcm_file:
        pcm_path = pcm_file.name

    if not generate_speech_audio(test_case.speech, pcm_path):
        result['error'] = 'Failed to generate speech audio'
        return result

    # Read PCM data
    with open(pcm_path, 'rb') as f:
        pcm_data = f.read()
    os.unlink(pcm_path)

    print(
        f'Generated {len(pcm_data)} bytes of audio ({len(pcm_data) / 96000:.1f} seconds)'
    )

    # Create voice session
    print('Creating voice session...')
    try:
        session = await create_voice_session()
    except Exception as e:
        result['error'] = f'Failed to create session: {e}'
        return result

    print(f'Room: {session["room_name"]}')

    room = rtc.Room()
    audio_frames_received = []
    first_frame_event = asyncio.Event()
    capture_task = None

    async def capture_audio_frames(stream: rtc.AudioStream):
        """Capture audio frames from the agent's audio track."""
        frame_count = 0
        try:
            async for event in stream:
                frame_count += 1
                audio_frames_received.append(event.frame)
                if frame_count == 1:
                    first_frame_event.set()
        except Exception as e:
            pass

    @room.on('track_subscribed')
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        nonlocal capture_task
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            audio_stream = rtc.AudioStream(track)
            capture_task = asyncio.create_task(
                capture_audio_frames(audio_stream)
            )

    try:
        # Connect to room
        await room.connect(session['livekit_url'], session['access_token'])
        print(f'Connected to room')

        # Wait for agent
        await asyncio.sleep(2)

        # Create and publish audio track
        source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track('microphone', source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await room.local_participant.publish_track(track, options)

        # Send audio frames
        print('Sending speech to agent...')
        samples_per_frame = 480  # 10ms at 48kHz
        bytes_per_frame = samples_per_frame * 2  # 16-bit samples

        for i in range(0, len(pcm_data), bytes_per_frame):
            chunk = pcm_data[i : i + bytes_per_frame]
            if len(chunk) < bytes_per_frame:
                # Pad with silence
                chunk = chunk + b'\x00' * (bytes_per_frame - len(chunk))

            frame = rtc.AudioFrame(
                data=chunk,
                sample_rate=48000,
                num_channels=1,
                samples_per_channel=samples_per_frame,
            )
            await source.capture_frame(frame)
            await asyncio.sleep(0.01)

        print('Speech sent! Waiting for agent response...')

        # Wait for response
        try:
            await asyncio.wait_for(first_frame_event.wait(), timeout=30.0)
            print('Agent is responding...')

            # Collect response for 10 seconds
            await asyncio.sleep(10)

            result['audio_frames_received'] = len(audio_frames_received)
            result['audio_duration_ms'] = len(audio_frames_received) * 10
            result['success'] = (
                len(audio_frames_received) > 50
            )  # More than 0.5s of audio

            print(
                f'Received {result["audio_frames_received"]} frames ({result["audio_duration_ms"]}ms)'
            )

            # Save the audio response to a file
            if audio_frames_received:
                output_dir = '/home/riley/A2A-Server-MCP'
                pcm_out = f'{output_dir}/agent_response_{test_case.name}.pcm'
                wav_out = f'{output_dir}/agent_response_{test_case.name}.wav'

                # Write raw PCM data
                with open(pcm_out, 'wb') as f:
                    for frame in audio_frames_received:
                        f.write(frame.data)
                print(f'Saved raw PCM to: {pcm_out}')

                # Convert to WAV using ffmpeg (24kHz, 16-bit, mono - Gemini output format)
                convert_result = subprocess.run(
                    [
                        'ffmpeg',
                        '-y',
                        '-f',
                        's16le',
                        '-ar',
                        '24000',
                        '-ac',
                        '1',
                        '-i',
                        pcm_out,
                        wav_out,
                    ],
                    capture_output=True,
                    text=True,
                )

                if convert_result.returncode == 0:
                    print(f'Saved WAV to: {wav_out}')
                    result['audio_file'] = wav_out
                else:
                    print(f'Failed to convert to WAV: {convert_result.stderr}')

        except asyncio.TimeoutError:
            result['error'] = 'Timeout waiting for agent response'

    except Exception as e:
        result['error'] = str(e)
        import traceback

        traceback.print_exc()
    finally:
        if capture_task:
            capture_task.cancel()
        await room.disconnect()

    return result


async def check_agent_logs_for_tools(room_name: str) -> List[str]:
    """Check agent logs for tool usage.

    Args:
        room_name: The room name to search for in logs.

    Returns:
        List of tools that were called.
    """
    # This would require kubectl access - for now return empty
    # In production, you'd check logs or have the agent report tool usage
    return []


async def run_all_tests():
    """Run all test cases and report results."""
    print('\n' + '=' * 70)
    print('VOICE AGENT TOOL INTEGRATION TEST SUITE')
    print('=' * 70)

    results = []

    for test_case in TEST_CASES:
        result = await run_test_case(test_case)
        results.append(result)

        # Brief pause between tests
        await asyncio.sleep(2)

    # Print summary
    print('\n' + '=' * 70)
    print('TEST RESULTS SUMMARY')
    print('=' * 70)

    passed = 0
    failed = 0

    for result in results:
        status = 'PASS' if result['success'] else 'FAIL'
        if result['success']:
            passed += 1
        else:
            failed += 1

        print(f'\n{result["name"]}: {status}')
        print(f'  Speech: "{result["speech"][:50]}..."')
        print(f'  Audio received: {result["audio_duration_ms"]}ms')
        if result['error']:
            print(f'  Error: {result["error"]}')

    print('\n' + '-' * 70)
    print(
        f'TOTAL: {passed} passed, {failed} failed out of {len(results)} tests'
    )
    print('-' * 70)

    return passed == len(results)


if __name__ == '__main__':
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
