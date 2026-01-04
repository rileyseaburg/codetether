#!/usr/bin/env python3
"""
Test script to send audio to the voice agent and receive a response.
"""

import asyncio
import struct
import math
import httpx
from livekit import rtc

API_URL = 'https://api.codetether.run'


async def create_voice_session() -> dict:
    """Create a voice session via the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'{API_URL}/v1/voice/sessions', json={'voice': 'puck'}, timeout=30.0
        )
        response.raise_for_status()
        return response.json()


async def test_voice_agent():
    """Connect to LiveKit room and send audio to the agent."""
    print('Creating voice session...')
    session = await create_voice_session()
    print(f'Session created:')
    print(f'  Room: {session["room_name"]}')
    print(f'  LiveKit URL: {session["livekit_url"]}')

    room = rtc.Room()

    # Track received audio
    audio_frames_received = []
    audio_stream = None
    first_frame_event = asyncio.Event()
    capture_task = None

    async def capture_audio_frames(stream: rtc.AudioStream):
        """Capture audio frames from the agent's audio track."""
        nonlocal audio_frames_received
        frame_count = 0
        try:
            async for event in stream:
                frame_count += 1
                audio_frames_received.append(event.frame)
                if frame_count == 1:
                    print(f'>>> FIRST AUDIO FRAME RECEIVED FROM AGENT! <<<')
                    first_frame_event.set()
                if frame_count % 100 == 0:
                    print(f'Received {frame_count} audio frames from agent...')
        except Exception as e:
            print(f'Audio capture ended: {e}')

    @room.on('track_subscribed')
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        nonlocal audio_stream, capture_task
        print(f'Track subscribed: {track.kind} from {participant.identity}')
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print('>>> SUBSCRIBED TO AGENT AUDIO TRACK <<<')
            # Create audio stream to capture frames
            audio_stream = rtc.AudioStream(track)
            capture_task = asyncio.create_task(
                capture_audio_frames(audio_stream)
            )

    @room.on('participant_connected')
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print(f'Participant connected: {participant.identity}')

    @room.on('disconnected')
    def on_disconnected():
        print('Disconnected from room')

    try:
        print(f'\nConnecting to room {session["room_name"]}...')
        await room.connect(session['livekit_url'], session['access_token'])
        print(
            f'Connected! Local participant: {room.local_participant.identity}'
        )

        # List existing participants
        for identity, participant in room.remote_participants.items():
            print(f'Remote participant already in room: {identity}')

        # Wait a moment for the agent to detect us
        print('\nWaiting for agent to initialize...')
        await asyncio.sleep(3)

        # Create and publish an audio track
        print('\nCreating audio source...')
        source = rtc.AudioSource(sample_rate=48000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track('microphone', source)

        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE

        print('Publishing audio track...')
        publication = await room.local_participant.publish_track(track, options)
        print(f'Audio track published: {publication.sid}')

        # Generate and send audio frames
        print('\nSending audio (simulated speech - 3 seconds)...')

        # Generate 3 seconds of audio in chunks
        sample_rate = 48000
        samples_per_frame = 480  # 10ms at 48kHz
        total_duration = 3.0
        total_samples = int(sample_rate * total_duration)

        for frame_start in range(0, total_samples, samples_per_frame):
            samples = []
            for i in range(samples_per_frame):
                sample_idx = frame_start + i
                t = sample_idx / sample_rate
                # Create a varying tone to simulate speech-like audio
                freq = 200 + 200 * math.sin(2 * math.pi * 2 * t)
                envelope = min(
                    1.0, sample_idx / 4800, (total_samples - sample_idx) / 4800
                )
                sample = int(
                    32767 * envelope * 0.3 * math.sin(2 * math.pi * freq * t)
                )
                samples.append(sample)

            frame = rtc.AudioFrame(
                data=struct.pack(f'<{len(samples)}h', *samples),
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=samples_per_frame,
            )
            await source.capture_frame(frame)
            await asyncio.sleep(0.01)  # 10ms per frame

        print('Audio sent! Waiting for agent response...')

        # Wait for first audio frame from agent
        try:
            await asyncio.wait_for(first_frame_event.wait(), timeout=30.0)
            print('\n=== AGENT IS RESPONDING WITH AUDIO! ===')

            # Wait to collect more audio frames
            print('Collecting agent audio for 10 seconds...')
            await asyncio.sleep(10)

            # Report results
            total_frames = len(audio_frames_received)
            if total_frames > 0:
                # Calculate total audio duration
                # Each frame is 10ms at 48kHz (480 samples)
                total_duration_ms = total_frames * 10
                print(f'\n=== SUCCESS: AGENT RESPONDED! ===')
                print(f'Total audio frames received: {total_frames}')
                print(
                    f'Total audio duration: {total_duration_ms}ms ({total_duration_ms / 1000:.1f} seconds)'
                )

                # Check if we got meaningful audio (more than just silence)
                if total_frames > 50:  # More than 0.5 seconds of audio
                    print('Agent produced substantial audio response!')
                else:
                    print('Warning: Agent audio was very short')
            else:
                print('\n=== FAILURE: No audio frames captured ===')

        except asyncio.TimeoutError:
            print(
                '\n=== TIMEOUT: No audio response from agent within 30 seconds ==='
            )

            # Debug: list participants and their tracks
            print('\nDebug info:')
            print(
                f'Remote participants: {list(room.remote_participants.keys())}'
            )
            for identity, participant in room.remote_participants.items():
                print(f'  {identity}:')
                for pub in participant.track_publications.values():
                    print(
                        f'    Track: {pub.kind} - {pub.source} - subscribed: {pub.subscribed}'
                    )

    except Exception as e:
        print(f'Error: {e}')
        import traceback

        traceback.print_exc()
    finally:
        if capture_task:
            capture_task.cancel()
        print('\nDisconnecting...')
        await room.disconnect()
        print('Done!')


if __name__ == '__main__':
    asyncio.run(test_voice_agent())
