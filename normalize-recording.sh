#!/bin/sh
# Chuan hoa file ghi hinh MP4 tu SRS:
# "Nem ca cai file .mp4 len tren ma khong sua gi ca"
# Giu nguyen 100% video va audio goc (khong re-encode, khong resample, khong can thiep vao am thanh/hinh anh),
# chi sap xep atom +faststart de trinh duyet web / mobile phat ngay tuc thi.
set -eu

file=${1:?Usage: normalize-recording.sh recording.mp4}
marker="$file.avsync-v1"
temporary="$file.sync.tmp.mp4"

[ -f "$file" ] || exit 0
[ ! -f "$marker" ] || exit 0
case "$file" in *.tmp.mp4|*_fixed.mp4) exit 0 ;; esac

# Kiem tra file da ket thuc ghi hinh hop le
before=$(stat -c '%s:%y' "$file" 2>/dev/null || echo "")
duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$file" 2>/dev/null) || exit 0
case "$duration" in ''|N/A) exit 0 ;; esac

trap 'rm -f "$temporary"' EXIT HUP INT TERM

# Chi stream-copy (-c copy) va dua moov atom len dau (+faststart).
# TUYET DOI KHONG re-encode hay resample am thanh.
if ffmpeg -y -nostdin -hide_banner -loglevel warning -i "$file" \
    -c copy -movflags +faststart "$temporary" 2>/dev/null; then
    # Dam bao file goc khong bi ghi de them trong luc copy
    current_stat=$(stat -c '%s:%y' "$file" 2>/dev/null || echo "")
    if [ "$before" = "$current_stat" ]; then
        touch -r "$file" "$temporary"
        mv -f "$temporary" "$file"
    fi
fi

touch "$marker"
