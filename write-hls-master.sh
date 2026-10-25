#!/bin/sh
set -eu

app=${1:-}
stream=${2:-}

# Stream names are used in paths and playlist URLs, so accept only the key charset
# already used by the application.
case "$app" in
  live) ;;
  *) exit 0 ;;
esac
case "$stream" in
  ''|*[!a-zA-Z0-9_.-]*) exit 0 ;;
esac

root=/usr/local/srs/objs/nginx/html
source_url="/live/${stream}.m3u8"
master_file="${root}/live/${stream}.master.m3u8"
temp_file="${master_file}.tmp"
source_rtmp="rtmp://127.0.0.1:1935/live/${stream}"

mkdir -p "${root}/live"
attempt=0
while [ ! -f "${root}/live/${stream}.m3u8" ] && [ "$attempt" -lt 30 ]; do
	sleep 1
	attempt=$((attempt + 1))
done
[ -f "${root}/live/${stream}.m3u8" ] || exit 0

cleanup() {
	rm -f "$temp_file" "$master_file"
}
trap cleanup EXIT INT TERM

dimensions=$(/usr/bin/ffprobe -v error -rw_timeout 5000000 -select_streams v:0 \
	-show_entries stream=width,height -of csv=s=x:p=0 \
	"$source_rtmp" 2>/dev/null | head -n 1 || true)
case "$dimensions" in
	*[!0-9x]*|''|*x) dimensions=1280x720 ;;
esac
source_width=${dimensions%x*}
height=${dimensions#*x}

case "$height" in
	9[0-9][0-9]|[1-9][0-9][0-9][0-9]*) source_quality=1080; source_bw=5000000 ;;
	6[5-9][0-9]|[7-8][0-9][0-9]) source_quality=720; source_bw=2800000 ;;
	4[4-9][0-9]|[5-6][0-9][0-9]) source_quality=480; source_bw=1400000 ;;
	*) source_quality=360; source_bw=800000 ;;
esac

write_master() {
  {
    printf '#EXTM3U\n#EXT-X-VERSION:3\n'
    printf '#EXT-X-STREAM-INF:BANDWIDTH=%s,AVERAGE-BANDWIDTH=%s,RESOLUTION=%sx%s,NAME="%sp"\n%s\n' \
      "$source_bw" "$source_bw" "$source_width" "$height" "$source_quality" "$source_url"

    for rendition in 720p 480p 360p; do
      case "$rendition" in 720p) rung_height=720; rung_width=1280; rung_bw=2500000 ;;
        480p) rung_height=480; rung_width=854; rung_bw=1100000 ;;
        360p) rung_height=360; rung_width=640; rung_bw=700000 ;;
      esac
      if [ "$height" -gt "$rung_height" ] && [ -f "${root}/abr/${stream}_${rendition}.m3u8" ]; then
        printf '#EXT-X-STREAM-INF:BANDWIDTH=%s,AVERAGE-BANDWIDTH=%s,RESOLUTION=%sx%s,NAME="%s"\n/abr/%s_%s.m3u8\n' \
          "$rung_bw" "$rung_bw" "$rung_width" "$rung_height" "$rendition" "$stream" "$rendition"
      fi
    done
  } > "$temp_file"
  mv -f "$temp_file" "$master_file"
}

write_master

# SRS forks this helper on publish. Keep refreshing while the source is live so
# transcoded playlists that start a moment later are added to the master manifest.
while [ -f "${root}/live/${stream}.m3u8" ]; do
  sleep 1
  write_master
done
