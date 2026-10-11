# -*- coding: utf-8 -*-
# 切换模型的小工具：运行它，输入 1 或 2，自动帮你改好 config.py
# 运行：在 Cursor 里点 ▶，或在终端输入 python3 scripts/switch_model.py

from pathlib import Path

config_path = Path(__file__).parent / "config.py"
text = config_path.read_text(encoding="utf-8")

current = "云端 DeepSeek" if 'MODEL_SOURCE = "cloud"' in text else "本地 LM Studio"
print("当前模型源：", current)
print()
print("请选择要切换到的模型：")
print("  1 = 云端 DeepSeek（质量高，花 API 的钱）")
print("  2 = 本地 LM Studio（免费，但需先打开本地服务器）")
choice = input("输入 1 或 2 后回车：").strip()

if choice == "1":
    new = 'MODEL_SOURCE = "cloud"'
elif choice == "2":
    new = 'MODEL_SOURCE = "local"'
else:
    print("输入无效，没有做任何修改。")
    raise SystemExit

if 'MODEL_SOURCE = "cloud"' in text:
    text = text.replace('MODEL_SOURCE = "cloud"', new)
elif 'MODEL_SOURCE = "local"' in text:
    text = text.replace('MODEL_SOURCE = "local"', new)
else:
    print("没有找到 MODEL_SOURCE 设置，请检查 config.py。")
    raise SystemExit

config_path.write_text(text, encoding="utf-8")
print()
print("已切换为：", "云端 DeepSeek" if choice == "1" else "本地 LM Studio")
print("下次运行任何读取 config.py 的脚本，就会自动使用这个模型。")
