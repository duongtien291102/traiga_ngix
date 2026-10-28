#!/bin/sh
# Normalize a completed SRS MP4 for browser playback without re-encoding video.
set -eu

file=${1:?Usage: normalize-recording.sh recording.mp4}
marker="$file.avsync-v1"
temporary="$file.sync.tmp.mp4"

[ -f "$file" ] || exit 0
[ ! -f "$marker" ] || exit 0
case "$file" in *.tmp.mp4|*_fixed.mp4) exit 0 ;; esac

# A quiet publisher can stop growing for a while. Require a finalized MP4
# (moov metadata), and check that the source stays unchanged through conversion.
before=$(stat -c '%s:%y' "$file")
duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$file") || exit 0
case "$duration" in ''|N/A) exit 0 ;; esac

trap 'rm -f "$temporary"' EXIT HUP INT TERM
# Copying AAC preserves irregular packet durations from SRS. Browsers can play
# those samples continuously, making speech run ahead of the video. Materialize
# the timestamp gaps in the audio samples before encoding a regular AAC timeline.
ffmpeg -y -nostdin -hide_banner -loglevel warning -i "$file" \
    -map 0:v:0 -map '0:a:0?' -c:v copy -c:a aac -b:a 128k \
    -af 'aresample=async=1000:first_pts=0' -movflags +faststart "$temporary"

[ "$before" = "$(stat -c '%s:%y' "$file")" ] || exit 0
# Preserve the recording's age for the seven-day retention policy.
touch -r "$file" "$temporary"
mv -f "$temporary" "$file"
touch "$marker"
