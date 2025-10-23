import os
from PIL import Image

def convert_png_to_jpg(input_dir, recursive=False, quality=100, background=(255, 255, 255)):
    """
    将指定目录下的PNG文件转换为JPG格式
    :param input_dir: 目标文件夹路径
    :param recursive: 是否递归处理子目录（True/False）
    :param quality: JPG质量（1-100，100为最高）
    :param background: PNG透明区域填充色（默认白色RGB(255,255,255)）
    """
    # 遍历目录
    for root, dirs, files in os.walk(input_dir):
        for file in files:
            # 筛选PNG文件（不区分大小写，如.png/.PNG）
            if file.lower().endswith('.png'):
                png_path = os.path.join(root, file)
                # 生成JPG文件名（替换后缀）
                jpg_filename = os.path.splitext(file)[0] + '.jpg'
                jpg_path = os.path.join(root, jpg_filename)
                
                # 避免重复转换（如果JPG已存在则跳过）
                if os.path.exists(jpg_path):
                    print(f"已存在，跳过：{jpg_path}")
                    continue
                
                try:
                    # 打开PNG图片
                    with Image.open(png_path) as img:
                        # 处理透明通道（PNG可能有alpha通道，JPG不支持）
                        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                            # 创建白色背景的新图片
                            background_img = Image.new(img.mode[:-1], img.size, background)
                            # 将PNG粘贴到背景上（保留非透明区域）
                            background_img.paste(img, img.split()[-1])  # 使用alpha通道作为掩码
                            img = background_img.convert('RGB')
                        else:
                            # 无透明通道，直接转换为RGB
                            img = img.convert('RGB')
                        
                        # 保存为JPG（最高质量）
                        img.save(jpg_path, 'JPEG', quality=quality, optimize=True)
                        print(f"转换成功：{png_path} -> {jpg_path}")
                except Exception as e:
                    print(f"转换失败 {png_path}：{str(e)}")
        
        # 如果不递归，只处理当前目录后退出
        if not recursive:
            break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量将PNG转换为高质量JPG")
    parser.add_argument("--dir", default=".", help="目标文件夹（默认当前目录）")
    parser.add_argument("--recursive", action="store_true", help="是否递归处理子目录")
    parser.add_argument("--quality", type=int, default=100, help="JPG质量（1-100，默认100）")
    parser.add_argument("--bg", type=int, nargs=3, default=[255,255,255], 
                        help="透明区域填充色（RGB值，默认白色 255 255 255）")
    args = parser.parse_args()
    
    # 验证质量参数
    if not (1 <= args.quality <= 100):
        print("错误：质量参数必须在1-100之间")
        exit(1)
    
    # 验证背景色参数
    for c in args.bg:
        if not (0 <= c <= 255):
            print("错误：背景色RGB值必须在0-255之间")
            exit(1)
    
    # 执行转换
    convert_png_to_jpg(
        input_dir=args.dir,
        recursive=args.recursive,
        quality=args.quality,
        background=tuple(args.bg)
    )
    print("转换完成")