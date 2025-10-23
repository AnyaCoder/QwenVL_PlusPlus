import json
import re
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
from PIL import Image
import torch
from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor
from qwen_vl_utils import process_vision_info

def get_current_temperature(location: str, unit: str = "celsius"):
    """Get current temperature at a location.

    Args:
        location: The location to get the temperature for, in the format "City, State, Country".
        unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

    Returns:
        the temperature, the location, and the unit in a dict
    """
    return {
        "temperature": 26.1,
        "location": location,
        "unit": unit,
    }


def get_temperature_date(location: str, date: str, unit: str = "celsius"):
    """Get temperature at a location and date.

    Args:
        location: The location to get the temperature for, in the format "City, State, Country".
        date: The date to get the temperature for, in the format "Year-Month-Day".
        unit: The unit to return the temperature in. Defaults to "celsius". (choices: ["celsius", "fahrenheit"])

    Returns:
        the temperature, the location, the date and the unit in a dict
    """
    return {
        "temperature": 25.9,
        "location": location,
        "date": date,
        "unit": unit,
    }


# 工具列表
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Get current temperature at a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_temperature_date",
            "description": "Get temperature at a location and date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": 'The location to get the temperature for, in the format "City, State, Country".',
                    },
                    "date": {
                        "type": "string",
                        "description": 'The date to get the temperature for, in the format "Year-Month-Day".',
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": 'The unit to return the temperature in. Defaults to "celsius".',
                    },
                },
                "required": ["location", "date"],
            },
        },
    },
]

def get_function_by_name(function_name):
    """根据函数名获取对应的函数"""
    function_map = {
        "get_current_temperature": get_current_temperature,
        "get_temperature_date": get_temperature_date
    }
    return function_map.get(function_name)

def try_parse_tool_calls(content: str):
    """解析工具调用"""
    tool_calls = []
    offset = 0
    for i, m in enumerate(re.finditer(r"<tool_call>\n(.+)?\n</tool_call>", content)):
        if i == 0:
            offset = m.start()
        try:
            func = json.loads(m.group(1))
            tool_calls.append({"type": "function", "function": func})
            if isinstance(func["arguments"], str):
                func["arguments"] = json.loads(func["arguments"])
        except json.JSONDecodeError as e:
            print(f"Failed to parse tool calls: the content is {m.group(1)} and {e}")
            pass
    if tool_calls:
        if offset > 0 and content[:offset].strip():
            c = content[:offset]
        else: 
            c = ""
        return {"role": "assistant", "content": c, "tool_calls": tool_calls}
    return {"role": "assistant", "content": re.sub(r"<\|im_end\|>$", "", content)}

def main():
    # 使用正确的初始化代码
    
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        os.environ["LOCAL_MODEL"],
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
        device_map="auto",
    )
    
    processor = AutoProcessor.from_pretrained(os.environ["LOCAL_MODEL"])
    
    # 视频帧文件夹路径 - 请替换为实际路径
    video_frames_folder = "./videos/output_0_mp4"
    
    # 检查文件夹是否存在并获取帧文件
    if not os.path.exists(video_frames_folder):
        raise Exception
    
    try:
        frame_files = sorted([f for f in os.listdir(video_frames_folder) 
                            if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
        sample_frames = frame_files[:8]  # 取前8帧进行分析
        print(f"找到 {len(frame_files)} 个帧文件，使用 {len(sample_frames)} 个进行分析")
    except:
        print("无法读取帧文件，使用模拟数据演示")
        sample_frames = [f"frame_{i:05d}.jpg" for i in range(8)]
    
    # 构建包含图像和文本查询的消息
    messages = [
        {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant. Although you can't access network, you can still use tools provided.  \n\nCurrent Date: 2025-10-10"},
        {
            "role": "user",
            "content": [
                # *[{"type": "image", "image": f"file://{os.path.join(video_frames_folder, frame)}"} 
                #   for frame in sample_frames],
                {"type": "text", "text": 
                 "Although you can't access network, you can still use tools provided.What's the temperature in San Francisco now? How about tomorrow?"}
            ]
        }
    ]
    
    print("开始视频分析...")
    
    # 第一轮：让模型决定使用哪些工具
    text = processor.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    
    # 处理视觉输入
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = processor(
        text=[text],
        images=image_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)
    
    # 生成工具调用
    outputs = model.generate(**inputs, max_new_tokens=512)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, outputs)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]
    
    print("=== 模型生成的工具调用 ===")
    print(output_text)
    
    # 解析工具调用并执行
    assistant_message = try_parse_tool_calls(output_text)
    messages.append(assistant_message)
    
    tool_results = []
    
    if tool_calls := messages[-1].get("tool_calls", None):
        print(f"\n=== 执行 {len(tool_calls)} 个工具调用 ===")
        for i, tool_call in enumerate(tool_calls):
            if fn_call := tool_call.get("function"):
                fn_name: str = fn_call["name"]
                fn_args: dict = fn_call["arguments"]
                
                print(f"执行工具 {i+1}: {fn_name}")
                
                # 处理路径参数，确保是完整路径
                if 'frame_path' in fn_args:
                    fn_args['frame_path'] = os.path.join(video_frames_folder, os.path.basename(fn_args['frame_path']))
                elif 'frame_paths' in fn_args:
                    fn_args['frame_paths'] = [os.path.join(video_frames_folder, os.path.basename(fp)) 
                                            for fp in fn_args['frame_paths']]
                
                # 执行工具函数
                fn_result = get_function_by_name(fn_name)(**fn_args)
                fn_res: str = json.dumps(fn_result)
                tool_results.append(fn_result)
                
                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "content": fn_res,
                })
                
                print(f"工具 {fn_name} 执行完成")
    
    # 第二轮：获取最终分析结果
    print("\n=== 生成最终分析报告 ===")
    text = processor.apply_chat_template(
        messages, tools=TOOLS, tokenize=False, add_generation_prompt=True
    )
    
    # 重新处理视觉输入（保持相同的图像）
    image_inputs, video_inputs = process_vision_info(messages)
    
    inputs = processor(
        text=[text],
        images=image_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)
    
    outputs = model.generate(**inputs, max_new_tokens=1024)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, outputs)
    ]
    final_response = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]
    
    print("\n=== 最终分析结果 ===")
    print(final_response)
    
    # 添加最终响应到消息历史
    messages.append({"role": "assistant", "content": final_response})
    
    # 保存分析结果
    analysis_summary = {
        "video_frames_analyzed": sample_frames,
        "tools_used": [tool_call["function"]["name"] for tool_call in tool_calls] if tool_calls else [],
        "tool_results": tool_results,
        "final_analysis": final_response
    }
    
    with open("video_analysis_report.json", "w", encoding="utf-8") as f:
        json.dump(analysis_summary, f, indent=2, ensure_ascii=False)
    
    print("\n分析报告已保存到 video_analysis_report.json")
    
    return messages

if __name__ == "__main__":
    analysis_results = main()