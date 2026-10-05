"""Direct Gemini 3.1 Flash Live to LiveKit employee media bridge."""

from __future__ import annotations

import argparse
import asyncio
import os

from google import genai
from google.genai import types
from livekit import rtc

from apps.remote_employee.employee_presence import (
    animate_avatar,
    room_credentials,
)
from apps.remote_employee.gemini_config import MODEL, instructions


async def publish_gemini_audio(
    session: object,
    source: rtc.AudioSource,
    first_audio: asyncio.Event,
) -> None:
    """Continuously publish each completed Gemini response into LiveKit."""
    while True:
        async for response in session.receive():
            audio = getattr(response, 'data', None)
            if not audio:
                continue
            frame = rtc.AudioFrame(
                audio,
                sample_rate=24000,
                num_channels=1,
                samples_per_channel=len(audio) // 2,
            )
            await source.capture_frame(frame)
            first_audio.set()


async def forward_ceo_audio(
    track: rtc.Track,
    session: object,
    participant_identity: str,
) -> None:
    """Forward one subscribed CEO microphone to Gemini Live as PCM frames."""
    print(f'forwarding microphone from {participant_identity}', flush=True)
    stream = rtc.AudioStream(track, sample_rate=48000, num_channels=1)
    try:
        async for event in stream:
            frame = event.frame
            await session.send_realtime_input(
                audio=types.Blob(
                    data=bytes(frame.data),
                    mime_type=f'audio/pcm;rate={frame.sample_rate}',
                )
            )
    finally:
        await stream.aclose()


async def run(args: argparse.Namespace) -> None:  # noqa: PLR0915
    """Bridge CEO speech to Gemini and Gemini native audio back to LiveKit."""
    api_key = os.getenv('GOOGLE_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('GOOGLE_API_KEY must be injected from Vault')
    identity = f'employee:{args.employee_id}'
    credentials = await asyncio.to_thread(
        room_credentials, args.api_base, identity, args.name
    )
    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=['AUDIO'],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=args.voice
                )
            )
        ),
        system_instruction=instructions(args),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    async with client.aio.live.connect(model=MODEL, config=config) as gemini:
        room = rtc.Room()
        ceo_present = asyncio.Event()
        forwarding_tasks: set[asyncio.Task] = set()

        @room.on('participant_connected')
        def participant_connected(participant: rtc.RemoteParticipant) -> None:
            if not participant.identity.startswith('employee:'):
                print(f'CEO connected as {participant.identity}', flush=True)
                ceo_present.set()

        @room.on('track_subscribed')
        def track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ) -> None:
            del publication
            if (
                track.kind == rtc.TrackKind.KIND_AUDIO
                and not participant.identity.startswith('employee:')
            ):
                task = asyncio.create_task(
                    forward_ceo_audio(track, gemini, participant.identity)
                )
                forwarding_tasks.add(task)
                task.add_done_callback(forwarding_tasks.discard)

        await room.connect(credentials['url'], credentials['token'])
        for participant in room.remote_participants.values():
            participant_connected(participant)

        audio_source = rtc.AudioSource(24000, 1)
        audio_track = rtc.LocalAudioTrack.create_audio_track(
            f'{args.name}-gemini-live', audio_source
        )
        audio_options = rtc.TrackPublishOptions()
        audio_options.source = rtc.TrackSource.SOURCE_MICROPHONE
        audio_publication = await room.local_participant.publish_track(
            audio_track, audio_options
        )

        video_source = rtc.VideoSource(320, 180)
        video_track = rtc.LocalVideoTrack.create_video_track(
            f'{args.name}-avatar', video_source
        )
        video_options = rtc.TrackPublishOptions()
        video_options.source = rtc.TrackSource.SOURCE_CAMERA
        video_publication = await room.local_participant.publish_track(
            video_track, video_options
        )
        stop = asyncio.Event()
        video_task = asyncio.create_task(animate_avatar(video_source, stop))
        first_audio = asyncio.Event()
        receiver_task = asyncio.create_task(
            publish_gemini_audio(gemini, audio_source, first_audio)
        )
        try:
            print(
                f'employee={identity} room={credentials["room"]} model={MODEL} '
                f'voice={args.voice} audio_track={audio_publication.sid} '
                f'video_track={video_publication.sid}',
                flush=True,
            )
            await asyncio.wait_for(
                ceo_present.wait(), timeout=args.wait_for_ceo
            )
            await gemini.send_client_content(
                turns=types.Content(
                    role='user',
                    parts=[
                        types.Part(
                            text=(
                                'The CEO just entered the office. Say this '
                                'greeting naturally, then listen: '
                                f'{args.greeting}'
                            )
                        )
                    ],
                ),
                turn_complete=True,
            )
            await asyncio.wait_for(first_audio.wait(), timeout=30)
            print('Gemini 3.1 Live audio published successfully', flush=True)
            await asyncio.sleep(args.stay_seconds)
        finally:
            receiver_task.cancel()
            for task in forwarding_tasks:
                task.cancel()
            await asyncio.gather(
                receiver_task, *forwarding_tasks, return_exceptions=True
            )
            stop.set()
            await video_task
            await room.disconnect()


def main() -> None:
    """Parse one persisted employee profile and run its direct voice bridge."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--employee-id', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--role', required=True)
    parser.add_argument('--goal', required=True)
    parser.add_argument('--voice', required=True)
    parser.add_argument('--temperament', required=True)
    parser.add_argument('--cadence', required=True)
    parser.add_argument('--collaboration-style', required=True)
    parser.add_argument('--greeting', required=True)
    parser.add_argument('--api-base', default='http://127.0.0.1:8090')
    parser.add_argument('--wait-for-ceo', type=float, default=300)
    parser.add_argument('--stay-seconds', type=float, default=3600)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
