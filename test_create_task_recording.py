#!/usr/bin/env python3
"""
Test script to tell the voice agent to create a task and record the response.
"""

import asyncio
import subprocess
import tempfile
import os
import sys
import httpx
from livekit import rtc
from gtts import gTTS

API_URL = 'https://api.codetether.run'


def generate_speech_audio(text: str, output_path: str) -> bool:
    """Generate speech audio from text using gTTS and convert to PCM format."""
    try:
        with tempfile.NamedTemporaryFile(
            suffix='.mp3', delete=False
        ) as mp3_file:
            mp3_path = mp3_file.name

        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(mp3_path)

        result = subprocess.run(
            [
                'ffmpeg',
                '-y',
                '-i',
                mp3_path,
                '-ar',
                '48000',
                '-ac',
                '1',
                '-f',
                's16le',
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        os.unlink(mp3_path)
        return result.returncode == 0
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


async def test_create_task_with_recording():
    """Send speech to create a task and record the agent's response."""

    speech_text = 'Please create a new task called deploy voice agent to production with high priority'

    print('=' * 70)
    print('VOICE AGENT TASK CREATION TEST WITH RECORDING')
    print('=' * 70)
    print(f'\nSpeech to send: "{speech_text}"')

    # Generate speech audio
    print('\n1. Generating speech audio using gTTS...')
    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as pcm_file:
        pcm_path = pcm_file.name

    if not generate_speech_audio(speech_text, pcm_path):
        print('ERROR: Failed to generate speech audio')
        return False

    with open(pcm_path, 'rb') as f:
        pcm_data = f.read()
    os.unlink(pcm_path)
    print(
        f'   Generated {len(pcm_data)} bytes ({len(pcm_data) / 96000:.1f} seconds)'
    )

    # Create voice session
    print('\n2. Creating voice session...')
    session = await create_voice_session()
    print(f'   Room: {session["room_name"]}')
    print(f'   LiveKit URL: {session["livekit_url"]}')

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
                if frame_count % 100 == 0:
                    print(f'   Captured {frame_count} audio frames...')
        except Exception as e:
            pass

    @room.on('track_subscribed')
    def on_track_subscribed(track, publication, participant):
        nonlocal capture_task
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f'   Subscribed to agent audio track')
            audio_stream = rtc.AudioStream(track)
            capture_task = asyncio.create_task(
                capture_audio_frames(audio_stream)
            )

    try:
        # Connect to room
        print('\n3. Connecting to LiveKit room...')
        await room.connect(session['livekit_url'], session['access_token'])
        print(f'   Connected as: {room.local_participant.identity}')

        # Wait for agent
        await asyncio.sleep(2)

        # Create and publish audio track
        print('\n4. Publishing audio track...')
        source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track('microphone', source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await room.local_participant.publish_track(track, options)
        print('   Audio track published')

        # Send audio frames
        print('\n5. Sending speech to agent...')
        samples_per_frame = 480
        bytes_per_frame = samples_per_frame * 2

        for i in range(0, len(pcm_data), bytes_per_frame):
            chunk = pcm_data[i : i + bytes_per_frame]
            if len(chunk) < bytes_per_frame:
                chunk = chunk + b'\x00' * (bytes_per_frame - len(chunk))

            frame = rtc.AudioFrame(
                data=chunk,
                sample_rate=48000,
                num_channels=1,
                samples_per_channel=samples_per_frame,
            )
            await source.capture_frame(frame)
            await asyncio.sleep(0.01)

        print('   Speech sent!')

        # Wait for response
        print('\n6. Waiting for agent response...')
        try:
            await asyncio.wait_for(first_frame_event.wait(), timeout=30.0)
            print('   Agent is responding!')

            # Collect response for 15 seconds to get full response
            print('   Collecting audio for 15 seconds...')
            await asyncio.sleep(15)

            total_frames = len(audio_frames_received)
            duration_ms = total_frames * 10
            print(f'\n   Total frames received: {total_frames}')
            print(
                f'   Total duration: {duration_ms}ms ({duration_ms / 1000:.1f} seconds)'
            )

            # Save the audio response
            if audio_frames_received:
                output_dir = '/home/riley/A2A-Server-MCP'
                pcm_out = f'{output_dir}/agent_create_task_response.pcm'
                wav_out = f'{output_dir}/agent_create_task_response.wav'

                print(f'\n7. Saving agent response...')
                with open(pcm_out, 'wb') as f:
                    for frame in audio_frames_received:
                        f.write(frame.data)
                print(f'   Saved PCM: {pcm_out}')

                # Convert to WAV (24kHz, 16-bit, mono - Gemini output format)
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
                    # Get file size
                    wav_size = os.path.getsize(wav_out)
                    print(f'   Saved WAV: {wav_out} ({wav_size} bytes)')

                    print('\n' + '=' * 70)
                    print('SUCCESS! Agent response recorded.')
                    print(f'Audio file: {wav_out}')
                    print('=' * 70)
                    return True
                else:
                    print(f'   Failed to convert: {convert_result.stderr}')

        except asyncio.TimeoutError:
            print('   TIMEOUT: No response from agent within 30 seconds')

    except Exception as e:
        print(f'ERROR: {e}')
        import traceback

        traceback.print_exc()
    finally:
        if capture_task:
            capture_task.cancel()
        await room.disconnect()

    return False


if __name__ == '__main__':
    success = asyncio.run(test_create_task_with_recording())
    sys.exit(0 if success else 1)
