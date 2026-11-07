FROM ossrs/srs:6.0.195

USER root

# The stock image does not guarantee an FFmpeg binary; install one for SRS transcoding
# and ffprobe for detecting the incoming camera resolution in the master-playlist helper.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg python3 \
    && rm -rf /var/lib/apt/lists/*

COPY patch-srs-rtc.py /usr/local/bin/patch-srs-rtc.py
RUN python3 /usr/local/bin/patch-srs-rtc.py /usr/local/srs/objs/srs

COPY write-hls-master.sh /usr/local/bin/write-hls-master.sh
RUN chmod 0555 /usr/local/bin/write-hls-master.sh

COPY normalize-recording.sh /usr/local/bin/normalize-recording.sh
RUN chmod 0555 /usr/local/bin/normalize-recording.sh
