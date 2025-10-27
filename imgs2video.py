
import numpy as np
import os
import subprocess
import glob
import argparse


def images_to_av1_video_direct(
    image_dir: str,
    output_path: str,
    fps: float = 5,
    max_duration: float = 30,
    target_width: int = 640,
    target_height: int = 360
):
    """
    直接使用ffmpeg从图片创建视频（更高效的方法）
    """
    
    if not os.path.exists(image_dir):
        raise ValueError(f"图片目录不存在: {image_dir}")
 
    image_pattern = os.path.join(image_dir, "*.jpg")
    image_files = glob.glob(image_pattern)
    
    if not image_files:
        raise ValueError(f"在目录 {image_dir} 中未找到jpg图片")
    
    image_files.sort()
    
    print(f"找到 {len(image_files)} 张图片")
    
    max_frames = int(max_duration * fps)
    total_images = len(image_files)
    
    if total_images <= max_frames:
        sampled_files = image_files
        print(f"图片数量较少，使用所有 {total_images} 张图片")
    else:
        sampled_indices = np.linspace(0, total_images - 1, max_frames, dtype=int)
        sampled_files = [image_files[i] for i in sampled_indices]
        print(f"从 {total_images} 张图片中均匀采样 {max_frames} 张")
    
    # 创建文件列表供ffmpeg使用
    with open("input_files.txt", "w") as f:
        for file_path in sampled_files:
            f.write(f"file '{file_path}'\n")
            f.write(f"duration {1/fps}\n")
    
    try:
        # 使用ffmpeg直接处理
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "input_files.txt",
            "-vf", f"scale={target_width}:{target_height},drawtext=text='Frame %{{frame_num}}/{len(sampled_files)}':x=w-tw-10:y=h-th-10:fontcolor=yellow:fontsize=24:box=1:boxcolor=black",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            output_path
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"✅ 视频已保存: {output_path}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ ffmpeg处理失败: {e}")
        raise
    finally:
        # 清理临时文件
        if os.path.exists("input_files.txt"):
            os.remove("input_files.txt")


if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--image-dir", type=str, required=True)
    argparser.add_argument("--fps", type=str, default=5)
    argparser.add_argument("--max-duration", type=str, default=30)
    args = argparser.parse_args()
    
    image_dir = args.image_dir
    output_path = str(image_dir).strip("/") + ".mp4"
    fps = float(args.fps)
    max_duration = float(args.max_duration)
    
    try:
        images_to_av1_video_direct(
            image_dir=image_dir,
            output_path=output_path,
            fps=fps,
            max_duration=max_duration,
            target_width=640,
            target_height=360
        )

        
    except Exception as e:
        print(f"❌ 处理失败: {e}")