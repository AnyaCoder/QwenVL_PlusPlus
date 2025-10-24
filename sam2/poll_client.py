import base64
import json
import time
from io import BytesIO

import requests
from PIL import Image


class VideoAnalysisClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def submit_analysis_task(self, video_dir, user_query, **kwargs):
        """提交视频分析任务"""
        request_data = {
            "video_dir": video_dir,
            "user_query": user_query,
            "original_fps": kwargs.get("original_fps", 12.5),
            "target_fps": kwargs.get("target_fps", 2.0),
            "frames_needed": kwargs.get("frames_needed", 60),
            "grid_size": kwargs.get("grid_size", 16),
            "columns": kwargs.get("columns", 4),
        }

        response = requests.post(f"{self.base_url}/analyze_video", json=request_data)
        response.raise_for_status()

        return response.json()

    def poll_task_status(self, task_id, poll_interval=5, timeout=300):
        """轮询任务状态直到完成或超时"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(f"{self.base_url}/task_status/{task_id}")
            response.raise_for_status()

            task_info = response.json()
            status = task_info["status"]

            print(f"任务状态: {status}")

            if status == "done":
                return task_info
            elif status == "error":
                raise Exception(
                    f"任务处理失败: {task_info.get('result', 'Unknown error')}"
                )
            elif status == "queued" or status == "processing":
                time.sleep(poll_interval)
            else:
                raise Exception(f"未知的任务状态: {status}")

        raise TimeoutError(f"任务轮询超时 ({timeout}秒)")

    def save_base64_images(self, grid_images_base64, output_dir="output"):
        """将base64编码的图像保存到文件"""
        import os

        os.makedirs(output_dir, exist_ok=True)

        saved_files = []
        for i, img_base64 in enumerate(grid_images_base64):
            # 解码base64图像
            img_data = base64.b64decode(img_base64)
            img = Image.open(BytesIO(img_data))

            # 保存图像
            output_path = f"{output_dir}/grid_{i+1}.jpg"
            img.save(output_path)
            saved_files.append(output_path)
            print(f"保存网格图像: {output_path}")

        return saved_files

    def analyze_video_with_polling(self, video_dir, user_query, **kwargs):
        """完整的视频分析流程（提交任务 + 轮询结果）"""
        print("提交视频分析任务...")
        submit_result = self.submit_analysis_task(video_dir, user_query, **kwargs)
        task_id = submit_result["task_id"]

        print(f"任务已提交，ID: {task_id}")
        print("开始轮询任务状态...")

        # 轮询直到任务完成
        final_result = self.poll_task_status(task_id)

        # 提取分析结果
        analysis_result = final_result["result"]

        if analysis_result["status"] == "success":
            print(f"分析成功！共生成 {analysis_result['grid_count']} 个网格图像")
            print(f"检测到 {len(analysis_result['results'])} 个目标")

            # 保存网格图像
            if analysis_result["grid_images"]:
                saved_files = self.save_base64_images(
                    analysis_result["grid_images"], kwargs.get("output_dir", "output")
                )
                print(f"已保存 {len(saved_files)} 个网格图像")

            # 显示部分检测结果
            print("\n前5个检测结果:")
            for i, result in enumerate(analysis_result["results"][:5]):
                print(
                    f"  {i+1}. 时间: {result['time']}s, 标签: {result['label']}, "
                    f"边界框: {result['bbox_2d']}"
                )

            return analysis_result
        else:
            print(f"分析失败: {analysis_result['error']}")
            return analysis_result


def main():
    """使用示例"""
    client = VideoAnalysisClient()

    # 分析参数
    video_dir = "../videos/s050_camera_basler_south_50mm"
    user_query = "At first there is a white van stopped in the middle of the road. Track that van."

    # 可选参数
    analysis_params = {
        "original_fps": 12.5,
        "target_fps": 2.0,
        "frames_needed": 60,
        "grid_size": 16,
        "columns": 4,
        "output_dir": "analysis_results",
    }

    try:
        result = client.analyze_video_with_polling(
            video_dir, user_query, **analysis_params
        )

        # 可以进一步处理结果...
        if result["status"] == "success":
            # 保存检测结果到JSON文件
            with open("detection_results.json", "w") as f:
                json.dump(result["results"], f, indent=2)
            print("检测结果已保存到 detection_results.json")

    except Exception as e:
        print(f"视频分析失败: {e}")


if __name__ == "__main__":
    main()
