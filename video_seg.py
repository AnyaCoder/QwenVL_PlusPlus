import cv2
import numpy as np
import os
import subprocess

def process_video_segments(
    src_path: str,
    dst_dir: str,
    target_width: int,
    target_height: int,
    target_frames: int,
    target_fps: float,
    num_segments: int = 1,
    trim_head_ratio: float = 0.0,
    trim_tail_ratio: float = 0.0,
    reencode_h264: bool = True,
):
    """
    Process a video by splitting it into segments, trimming and sampling frames, 
    and writing each segment to a separate video file with frame annotations.

    Args:
        src_path (str): Path to input video.
        dst_dir (str): Directory to save output videos.
        target_width (int): Output video width.
        target_height (int): Output video height.
        target_frames (int): Number of frames per segment (<= original frames per segment).
        target_fps (float): Output video FPS.
        num_segments (int): Number of segments (K).
        trim_head_ratio (float): Ratio (0-1) of frames to trim from start of each segment.
        trim_tail_ratio (float): Ratio (0-1) of frames to trim from end of each segment.
        reencode_h264 (bool): Whether to reencode to H.264 (requires ffmpeg).

    Raises:
        ValueError: If invalid parameters or OpenCV fails to read/write.
    """
    font_scale = 1.0
    thickness_text = 3
    thickness_border = 5

    # ---- Check input validity ----
    if not os.path.exists(src_path):
        raise ValueError(f"Source video not found: {src_path}")
    if num_segments < 1:
        raise ValueError("num_segments must be >= 1")
    if not (0 <= trim_head_ratio < 1) or not (0 <= trim_tail_ratio < 1):
        raise ValueError("trim_head_ratio and trim_tail_ratio must be between 0 and 1")
    if trim_head_ratio + trim_tail_ratio >= 1.0:
        raise ValueError("Sum of trim_head_ratio and trim_tail_ratio must be < 1.0")

    os.makedirs(dst_dir, exist_ok=True)

    cap = cv2.VideoCapture(src_path)
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {src_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        raise ValueError("Source video has no frames")

    # Split frame ranges for each segment
    frames_per_segment = total_frames // num_segments
    if frames_per_segment <= 0:
        raise ValueError("Too many segments for this video length")

    font = cv2.FONT_HERSHEY_SIMPLEX
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # ---- Process each segment ----
    for seg_idx in range(num_segments):
        start = seg_idx * frames_per_segment
        end = start + frames_per_segment
        if seg_idx == num_segments - 1:
            end = total_frames  # include remaining frames

        # Trim head/tail ratios
        segment_length = end - start
        head_trim = int(segment_length * trim_head_ratio)
        tail_trim = int(segment_length * trim_tail_ratio)
        start += head_trim
        end -= tail_trim

        if start >= end:
            print(f"⚠️ Segment {seg_idx} skipped due to trimming too much.")
            continue

        # Sample frames uniformly
        segment_total = end - start
        if target_frames > segment_total:
            raise ValueError(f"target_frames ({target_frames}) exceeds frames in segment {seg_idx} ({segment_total})")

        frame_indices = np.linspace(start, end - 1, target_frames, dtype=int)

        temp_path = os.path.join(dst_dir, f"temp_seg_{seg_idx}.mp4")
        dst_path = os.path.join(dst_dir, f"output_{seg_idx}.mp4")

        out = cv2.VideoWriter(temp_path, fourcc, target_fps, (target_width, target_height))
        if not out.isOpened():
            raise ValueError(f"Failed to initialize VideoWriter for segment {seg_idx}")

        for i, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                print(f"⚠️ Failed to read frame {frame_idx}, skipped.")
                continue

            frame = cv2.resize(frame, (target_width, target_height))
            text = f"Frame: {i+1}"
            (tw, th), _ = cv2.getTextSize(text, font, 1.0, 3)
            x, y = target_width - tw - 10, th + 10
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness_border, cv2.LINE_AA)
            cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 255), thickness_text, cv2.LINE_AA)
            out.write(frame)

        out.release()

        # Optional re-encode to H.264
        if reencode_h264:
            try:
                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", temp_path,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    dst_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.remove(temp_path)
            except Exception as e:
                print(f"⚠️ FFmpeg re-encode failed for segment {seg_idx}: {e}")
                os.rename(temp_path, dst_path)

        print(f"✅ Segment {seg_idx} saved to {dst_path}")

    cap.release()
    print("🎬 All segments processed successfully.")


if __name__ == '__main__':
    process_video_segments(
        src_path="test.mp4",
        dst_dir="./",
        target_width=640,
        target_height=360,
        target_frames=25,
        target_fps=5,
        num_segments=4,
        trim_head_ratio=0.05,
        trim_tail_ratio=0.05,
        reencode_h264=True
    )
