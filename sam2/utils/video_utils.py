import os
import subprocess


def extract_frames_from_video(video_path: str):
    """使用FFmpeg从视频中提取帧并保存为JPEG文件"""
    video_dir = os.path.splitext(video_path)[0] + "_mp4"
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)

    cmd = f"ffmpeg -i {video_path} -q:v 2 -start_number 0 {video_dir}/%05d.jpg"
    subprocess.run(
        cmd,
        check=True,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return video_dir
