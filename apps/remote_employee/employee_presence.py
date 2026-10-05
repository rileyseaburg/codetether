"""Join a Remote Employee to the real LiveKit office with audio and video."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import urllib.request

from pathlib import Path

import numpy as np

from livekit import rtc


def room_credentials(api_base: str, identity: str, name: str) -> dict[str, str]:
    """Request a short-lived office token without exposing API credentials."""
    request = urllib.request.Request(
        f'{api_base.rstrip("/")}/api/office-token',
        data=json.dumps({'identity': identity, 'name': name}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def decoded_audio(path: Path) -> bytes:
    """Decode a greeting to 48 kHz mono PCM for a LiveKit audio source."""
    process = subprocess.run(
        [
            'ffmpeg',
            '-v',
            'error',
            '-i',
            str(path),
            '-f',
            's16le',
            '-acodec',
            'pcm_s16le',
            '-ar',
            '48000',
            '-ac',
            '1',
            '-',
        ],
        check=True,
        capture_output=True,
    )
    return process.stdout


async def publish_greeting(source: rtc.AudioSource, audio: bytes) -> None:
    """Publish PCM in real time so browser active-speaker state reacts."""
    samples_per_frame = 960
    frame_bytes = samples_per_frame * 2
    for offset in range(0, len(audio), frame_bytes):
        chunk = audio[offset : offset + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk += b'\0' * (frame_bytes - len(chunk))
        frame = rtc.AudioFrame(chunk, 48000, 1, samples_per_frame)
        await source.capture_frame(frame)
        await asyncio.sleep(0.02)


async def animate_avatar(source: rtc.VideoSource, stop: asyncio.Event) -> None:
    """Publish a small animated avatar feed as real video frames."""
    width, height = 320, 180
    x = np.arange(width, dtype=np.uint16)[None, :]
    y = np.arange(height, dtype=np.uint16)[:, None]
    frame_number = 0
    while not stop.is_set():
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[:, :, 0] = (x + frame_number * 3) % 120 + 30
        rgba[:, :, 1] = (y + frame_number * 2) % 130 + 90
        rgba[:, :, 2] = ((x // 2 + y // 2) + frame_number * 4) % 100 + 120
        rgba[:, :, 3] = 255
        # A bright center block remains legible even in tiny participant tiles.
        rgba[48:132, 118:202, :3] = (70, 232, 213)
        source.capture_frame(
            rtc.VideoFrame(
                width, height, rtc.VideoBufferType.RGBA, rgba.tobytes()
            )
        )
        frame_number += 1
        await asyncio.sleep(0.1)


async def run(args: argparse.Namespace) -> None:
    """Connect, wait for the CEO, greet once, and maintain avatar presence."""
    identity = f'employee:{args.employee_id}'
    credentials = await asyncio.to_thread(
        room_credentials, args.api_base, identity, args.name
    )
    room = rtc.Room()
    ceo_present = asyncio.Event()

    @room.on('participant_connected')
    def participant_connected(participant: rtc.RemoteParticipant) -> None:
        if not participant.identity.startswith('employee:'):
            print(
                f'CEO joined as {participant.identity}; greeting now',
                flush=True,
            )
            ceo_present.set()

    await room.connect(credentials['url'], credentials['token'])
    for participant in room.remote_participants.values():
        participant_connected(participant)

    audio_source = rtc.AudioSource(48000, 1)
    video_source = rtc.VideoSource(320, 180)
    audio_track = rtc.LocalAudioTrack.create_audio_track(
        'employee-greeting', audio_source
    )
    video_track = rtc.LocalVideoTrack.create_video_track(
        'employee-avatar', video_source
    )
    audio_options = rtc.TrackPublishOptions()
    audio_options.source = rtc.TrackSource.SOURCE_MICROPHONE
    video_options = rtc.TrackPublishOptions()
    video_options.source = rtc.TrackSource.SOURCE_CAMERA
    audio_publication = await room.local_participant.publish_track(
        audio_track, audio_options
    )
    video_publication = await room.local_participant.publish_track(
        video_track, video_options
    )
    print(
        f'employee={identity} room={credentials["room"]} '
        f'audio_track={audio_publication.sid} '
        f'video_track={video_publication.sid}',
        flush=True,
    )

    stop = asyncio.Event()
    video_task = asyncio.create_task(animate_avatar(video_source, stop))
    try:
        await asyncio.wait_for(ceo_present.wait(), timeout=args.wait_for_ceo)
        audio = await asyncio.to_thread(decoded_audio, args.greeting)
        await publish_greeting(audio_source, audio)
        print('greeting published successfully', flush=True)
        await asyncio.sleep(args.stay_seconds)
    finally:
        stop.set()
        await video_task
        await room.disconnect()


def main() -> None:
    """Parse the employee presence CLI and run its async media loop."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--employee-id', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--greeting', required=True, type=Path)
    parser.add_argument('--api-base', default='http://127.0.0.1:8090')
    parser.add_argument('--wait-for-ceo', type=float, default=300)
    parser.add_argument('--stay-seconds', type=float, default=900)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
