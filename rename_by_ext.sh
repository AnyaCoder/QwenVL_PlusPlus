#!/bin/bash

# 检查是否提供了目录参数，默认使用当前目录
target_dir="${1:-.}"

# 检查目录是否存在
if [ ! -d "$target_dir" ]; then
    echo "错误：目录 '$target_dir' 不存在"
    exit 1
fi

# 获取所有非目录文件（非递归），并按名称排序（保持系统默认排序）
files=$(find "$target_dir" -maxdepth 1 -type f | sort)

# 按文件后缀分组处理
declare -A ext_groups  # 用关联数组存储不同后缀的文件列表

# 遍历所有文件，按后缀分组
while IFS= read -r file; do
    # 获取文件名（不含路径）
    filename=$(basename "$file")
    
    # 提取文件后缀（不包含.）
    if [[ "$filename" == *.* ]]; then
        ext="${filename##*.}"
    else
        ext="no_extension"  # 无后缀文件的统一标识
    fi
    
    # 将文件路径添加到对应后缀的分组中
    ext_groups["$ext"]+="$file"$'\n'
done <<< "$files"

# 处理每个后缀分组
for ext in "${!ext_groups[@]}"; do
    echo "处理后缀: ${ext}"
    
    # 获取该后缀的文件列表并去除空行
    file_list=$(echo -e "${ext_groups[$ext]}" | sed '/^$/d')
    
    # 统计文件数量
    count=$(echo -e "$file_list" | wc -l)
    echo "  共 $count 个文件"
    
    # 遍历文件并按顺序重命名
    index=0
    while IFS= read -r file; do
        # 生成新文件名（5位数字，不足补0）
        new_name=$(printf "%05d.%s" "$index" "$ext")
        new_path="$target_dir/$new_name"
        
        # 避免文件名冲突（理论上不应发生，因为是按顺序生成）
        if [ -e "$new_path" ]; then
            echo "  警告：文件 '$new_path' 已存在，跳过重命名"
        else
            # 执行重命名
            mv -v "$file" "$new_path"
        fi
        
        index=$((index + 1))
    done <<< "$file_list"
    
    echo "  处理完成"
    echo
done

echo "所有文件处理完毕"