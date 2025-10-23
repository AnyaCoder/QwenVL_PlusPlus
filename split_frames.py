import os
import re
import argparse
from typing import List, Tuple
from PIL import Image  # 用于图像分辨率调整


def get_sorted_frames(input_dir: str) -> List[Tuple[int, str]]:
    """读取输入目录中按{05d}.jpg命名的帧文件，按序号排序"""
    frame_pattern = re.compile(r'^(\d{5})\.jpg$')  # 匹配5位数字.jpg格式
    frames = []
    
    for filename in os.listdir(input_dir):
        match = frame_pattern.match(filename)
        if match:
            frame_idx = int(match.group(1))  # 提取帧序号
            frames.append((frame_idx, filename))
    
    # 按帧序号升序排序（确保顺序正确）
    frames.sort(key=lambda x: x[0])
    return frames


def split_into_parts(total: int, k: int) -> List[Tuple[int, int]]:
    """将总数为total的元素均匀分割为k部分，返回每部分的[起始索引, 结束索引)"""
    if k <= 0:
        raise ValueError("K必须为正整数")
    if total < k:
        raise ValueError(f"总帧数({total})小于分割数({k})，无法均匀分割")
    
    base = total // k
    remainder = total % k  # 前remainder部分多1帧
    parts = []
    start = 0
    
    for i in range(k):
        end = start + base + (1 if i < remainder else 0)
        parts.append((start, end))
        start = end
    
    return parts


def select_uniform_frames(part_frames: List[Tuple[int, str]], m: int) -> List[Tuple[int, str]]:
    """从部分帧中均匀选择m帧（不超过该部分总帧数）"""
    m_actual = min(m, len(part_frames))
    if m_actual <= 0:
        return []
    
    # 计算均匀选取的索引（相对当前部分）
    if m_actual == 1:
        selected_indices = [0]
    else:
        interval = (len(part_frames) - 1) / (m_actual - 1)  # 均匀间隔
        selected_indices = [int(round(i * interval)) for i in range(m_actual)]
    
    # 根据索引获取选中的帧
    return [part_frames[idx] for idx in selected_indices]


def resize_and_save(orig_path: str, new_path: str, width: int = None, height: int = None) -> bool:
    """
    读取原图，调整分辨率（可选）并保存
    :param orig_path: 原始图像路径
    :param new_path: 新图像保存路径
    :param width: 目标宽度（像素），为None则不调整
    :param height: 目标高度（像素），为None则不调整
    :return: 成功返回True，失败返回False
    """
    try:
        with Image.open(orig_path) as img:
            # 调整分辨率（如果指定了宽高）
            if width is not None and height is not None:
                # 使用Lanczos滤镜进行高质量缩放
                img = img.resize((width, height), Image.Resampling.LANCZOS)
            
            # 保存为JPG（保持高质量）
            img.save(new_path, "JPEG", quality=95, optimize=True)
        return True
    except Exception as e:
        print(f"  处理失败{os.path.basename(orig_path)}：{str(e)}")
        return False


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="将有序帧文件分割为K部分，每部分保留m帧，并支持调整分辨率")
    parser.add_argument("--input", default=".", help="输入帧文件夹（默认当前目录）")
    parser.add_argument("--output", required=True, help="输出文件夹（必须指定）")
    parser.add_argument("--K", type=int, required=True, help="分割的部分数（正整数）")
    parser.add_argument("--m", type=int, required=True, help="每部分保留的帧数（正整数）")
    parser.add_argument("--width", type=int, help="目标宽度（像素），不指定则保持原分辨率")
    parser.add_argument("--height", type=int, help="目标高度（像素），不指定则保持原分辨率")
    args = parser.parse_args()

    # 验证参数
    if not os.path.isdir(args.input):
        print(f"错误：输入目录'{args.input}'不存在")
        return
    if args.K <= 0 or args.m <= 0:
        print("错误：K和m必须为正整数")
        return
    # 验证分辨率参数（要么都不指定，要么都指定）
    if (args.width is None) != (args.height is None):
        print("错误：--width和--height必须同时指定或同时不指定")
        return
    if args.width is not None and (args.width <= 0 or args.height <= 0):
        print("错误：宽度和高度必须为正整数")
        return

    # 读取并排序帧文件
    frames = get_sorted_frames(args.input)
    total_frames = len(frames)
    if total_frames == 0:
        print(f"错误：输入目录'{args.input}'中没有符合格式的帧文件（{{05d}}.jpg）")
        return
    
    # 显示处理信息
    resize_info = f"（调整分辨率为{args.width}x{args.height}）" if args.width else "（保持原分辨率）"
    print(f"发现{total_frames}个帧文件，准备分割为{args.K}部分，每部分保留{args.m}帧{resize_info}...")

    # 分割为K部分
    try:
        parts = split_into_parts(total_frames, args.K)
    except ValueError as e:
        print(f"错误：{e}")
        return

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 处理每个部分
    for part_idx, (start, end) in enumerate(parts):
        # 当前部分的帧（全局索引[start, end)）
        part_frames = frames[start:end]
        part_total = len(part_frames)
        print(f"\n处理第{part_idx+1}/{args.K}部分：共{part_total}帧，计划保留{min(args.m, part_total)}帧")

        # 均匀选择m帧
        selected_frames = select_uniform_frames(part_frames, args.m)
        if not selected_frames:
            print("  警告：该部分无帧可保留，跳过")
            continue

        # 创建子文件夹（如part_00000）
        part_dir = os.path.join(args.output, f"part_{part_idx:05d}")
        os.makedirs(part_dir, exist_ok=True)
        print(f"  子文件夹：{part_dir}")

        # 调整分辨率并重新命名帧（按00000.jpg开始连续编号）
        for new_idx, (orig_idx, orig_filename) in enumerate(selected_frames):
            orig_path = os.path.join(args.input, orig_filename)
            new_filename = f"{new_idx:05d}.jpg"
            new_path = os.path.join(part_dir, new_filename)
            
            if resize_and_save(orig_path, new_path, args.width, args.height):
                print(f"  处理完成：{orig_filename} -> {new_filename} {resize_info}")

    print("\n所有部分处理完成")


if __name__ == "__main__":
    main()