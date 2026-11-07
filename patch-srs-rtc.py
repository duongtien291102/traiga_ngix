#!/usr/bin/env python3
"""Patch SRS 6.0.195 WebRTC receiver track A/V sync initialization.

Fixes three root causes of WebRTC-to-RTMP/HLS/DVR audio delay and missing
startup audio in SRS 6.0.195:
1. SrsRtcRecvTrack constructor: initializes rate_ immediately from track type
   (48.0 ticks/ms for 48kHz Opus audio, 90.0 ticks/ms for 90kHz video) instead
   of leaving rate_ = 0.0 until two RTCP Sender Reports arrive (which drops the
   first 4.5-6.5 seconds of browser WebRTC audio).
2. SrsRtcRecvTrack::cal_avsync_time: anchors the track's first RTP packet to
   srs_update_system_time() / 1000 (ms) and computes subsequent timestamps from
   32-bit signed RTP timestamp deltas divided by rate_.
3. SrsRtcRecvTrack::update_send_report_time: updates RTCP SR metadata for
   Receiver Reports without overwriting the active RTP clock anchor or rate_.
4. SrsRtmpJitter::correct (ZERO mode): clamps negative relative timestamps to 0
   so unsigned 32-bit MP4/FLV DTS casts never underflow.
"""
import pathlib
import sys


# 1. SrsRtcRecvTrack::SrsRtcRecvTrack (offset 0x5d19b2, 55 bytes)
CTOR_OLD = bytes.fromhex(
    "488b45e8"                  # mov -0x18(%rbp), %rax
    "48c7405000000000"          # movq $0, 0x50(%rax)
    "488b45e8"                  # mov -0x18(%rbp), %rax
    "48c7407800000000"          # movq $0, 0x78(%rax)
    "488b45e8"                  # mov -0x18(%rbp), %rax
    "660fefc0"                  # pxor %xmm0, %xmm0
    "f20f118080000000"          # movsd %xmm0, 0x80(%rax)
    "488b45e8"                  # mov -0x18(%rbp), %rax
    "48c7808800000000000000"    # movq $0, 0x88(%rax)
)
CTOR_NEW = bytes.fromhex(
    "488b45e8"                  # mov -0x18(%rbp), %rax
    "31d2"                      # xor %edx, %edx
    "48895050"                  # mov %rdx, 0x50(%rax)
    "48895060"                  # mov %rdx, 0x60(%rax) (base_sys_ms_ = 0)
    "48895078"                  # mov %rdx, 0x78(%rax) (base_rtp_time_ = 0)
    "48899088000000"            # mov %rdx, 0x88(%rax)
    "48899080000000"            # mov %rdx, 0x80(%rax)
    "ba00805640"                # mov $0x40568000, %edx (90.0 upper32)
    "b900004840"                # mov $0x40480000, %ecx (48.0 upper32)
    "807dd400"                  # cmpb $0, -0x2c(%rbp)  (is_audio)
    "0f45d1"                    # cmovne %ecx, %edx
    "899084000000"              # mov %edx, 0x84(%rax)
)

# 2. SrsRtcRecvTrack::update_send_report_time (offset 0x5d1bce, 347 bytes)
SR_OLD = bytes.fromhex(
    "f30f1efa554889e54883ec4048897dd8488975d08955cc"
    "488b45d8488d5030488b45d84883c0584889d64889c7e8ae240000"
    "488b45d8488b5050488b45d848895078"
    "488b45d8488d5030488b45d04889c64889d7e887240000"
    "8b55cc488b45d848895050e82081d6ff4889c2488b45d848899088000000"
    "488b45d8488b40784885c00f8ed1000000488b45d8488b40384885c07807"
    "f2480f2ac0eb154889c248d1ea83e0014809c2f2480f2ac2f20f58c0488b"
    "45d8488b40604885c07807f2480f2ac8eb154889c248d1ea83e0014809c2"
    "f2480f2acaf20f58c9f20f5cc1f20f1145e8488b45e866480f6ec0e88021"
    "000083f8020f94c084c0755d488b45d8488b4050f2480f2ac0488b45d848"
    "8b4078f2480f2ac8f20f5cc1f20f1145f0f20f1045f0f20f5e45e8e8f535"
    "d4ff66480f7ec0488945f8f20f1045f8660fefc9660f2fc17614488b45d8"
    "f20f1045f8f20f118080000000eb0190c9c3"
)
SR_HEAD = (
    bytes.fromhex("f30f1efa554889e54883ec4048897dd8488975d08955cc")
    + (b"\x90" * 43)
    + bytes.fromhex(
        "488b45d8488d5030488b45d04889c64889d7e887240000"
        "8b55cc488b45d848895050e82081d6ff4889c2488b45d848899088000000"
        "c9c3"
    )
)
SR_NEW = SR_HEAD + (b"\x90" * (len(SR_OLD) - len(SR_HEAD)))

# 3. SrsRtcRecvTrack::cal_avsync_time (offset 0x5d1d2a, 167 bytes)
CAL_OLD = bytes.fromhex(
    "f30f1efa554889e54883ec2048897de88975e4488b45e8f20f108880000000"
    "f20f1005cf7a3d00660f2fc1760948c7c0ffffffffeb6f8b55e4488b45e848"
    "8b40504829c24889d0f2480f2ac0488b45e8f20f108880000000f20f5ec1e8"
    "6535d4ff66480f7ec0488945f0488b45e8488b40384885c07807f2480f2ac0"
    "eb154889c248d1ea83e0014809c2f2480f2ac2f20f58c0f20f5845f0f2480f"
    "2cc0488945f8488b45f8c9c3"
)
CAL_BODY = bytes.fromhex(
    "f30f1efa"          # endbr64
    "55"                # push %rbp
    "4889e5"            # mov %rsp, %rbp
    "53"                # push %rbx
    "4883ec18"          # sub $0x18, %rsp
    "4889fb"            # mov %rdi, %rbx
    "8975e4"            # mov %esi, -0x1c(%rbp)
    "48837b6000"        # cmpq $0, 0x60(%rbx)
    "751a"              # jne +26 (.L_calc)
    "e80e80d6ff"        # call 0x339d57 (srs_update_system_time)
    "31d2"              # xor %edx, %edx
    "b9e8030000"        # mov $1000, %ecx
    "48f7f1"            # div %rcx
    "48894360"          # mov %rax, 0x60(%rbx)
    "8b45e4"            # mov -0x1c(%rbp), %eax
    "48894378"          # mov %rax, 0x78(%rbx)
    "8b45e4"            # .L_calc: mov -0x1c(%rbp), %eax
    "2b4378"            # sub 0x78(%rbx), %eax
    "f20f2ac0"          # cvtsi2sdl %eax, %xmm0
    "f20f5e8380000000"  # divsd 0x80(%rbx), %xmm0
    "f2480f2dc0"        # cvtsd2siq %xmm0, %rax
    "48034360"          # add 0x60(%rbx), %rax
    "4883c418"          # add $0x18, %rsp
    "5b"                # pop %rbx
    "5d"                # pop %rbp
    "c3"                # ret
)
CAL_NEW = CAL_BODY + (b"\x90" * (len(CAL_OLD) - len(CAL_BODY)))

# 4. SrsRtmpJitter::correct ZERO mode clamp (offset 0x44c6f6, 27 bytes)
JITTER_OLD = bytes.fromhex(
    "488b45d0"          # mov -0x30(%rbp), %rax
    "488b5008"          # mov 0x08(%rax), %rdx
    "488b45d8"          # mov -0x28(%rbp), %rax
    "488b4010"          # mov 0x10(%rax), %rax
    "4829c2"            # sub %rax, %rdx
    "488b45d0"          # mov -0x30(%rbp), %rax
    "48895008"          # mov %rdx, 0x08(%rax)
)
JITTER_NEW = bytes.fromhex(
    "488b45d0"          # mov -0x30(%rbp), %rax
    "488b5008"          # mov 0x08(%rax), %rdx
    "488b4dd8"          # mov -0x28(%rbp), %rcx
    "482b5110"          # sub 0x10(%rcx), %rdx
    "7902"              # jns +2
    "31d2"              # xor %edx, %edx
    "48895008"          # mov %rdx, 0x08(%rax)
    "909090"            # nop; nop; nop
)

PATCHES = [
    ("SrsRtcRecvTrack::ctor", CTOR_OLD, CTOR_NEW),
    ("SrsRtcRecvTrack::update_send_report_time", SR_OLD, SR_NEW),
    ("SrsRtcRecvTrack::cal_avsync_time", CAL_OLD, CAL_NEW),
    ("SrsRtmpJitter::correct", JITTER_OLD, JITTER_NEW),
]


def patch_binary(data: bytes) -> bytes:
    for name, old, new in PATCHES:
        assert len(old) == len(new), f"{name}: length mismatch ({len(old)} != {len(new)})"
        if new in data and old not in data:
            continue
        count = data.count(old)
        if count != 1:
            raise RuntimeError(f"{name}: expected 1 match, found {count}")
        data = data.replace(old, new, 1)
    return data


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /path/to/srs", file=sys.stderr)
        return 2
    target = pathlib.Path(sys.argv[1])
    original = target.read_bytes()
    patched = patch_binary(original)
    target.write_bytes(patched)
    print(f"Successfully patched {target} ({len(patched)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
