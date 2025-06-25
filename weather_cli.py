#!/usr/bin/env python3
"""
简洁的天气查询CLI
隐藏复杂的多代理协作日志，只显示关键步骤和结果
"""

import asyncio
import sys
import logging
from weather_team import WeatherAgentTeam

# 隐藏复杂的AutoGen日志
logging.getLogger("autogen_core").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.ERROR, format='')

class SimpleWeatherCLI:
    """简洁的天气查询命令行界面"""
    
    def __init__(self):
        self.team = None
        
    async def initialize(self):
        """初始化天气查询团队"""
        print("🤖 初始化天气查询系统...")
        try:
            # 使用静默模式初始化，避免重复的协作流程输出
            self.team = WeatherAgentTeam(verbose=False)
            await self.team.initialize()
            print("✅ 系统准备就绪！")
            print()
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            sys.exit(1)
    
    async def query_weather(self, user_input: str):
        """查询天气并显示简洁的协作过程"""
        print(f"🗣️  用户查询: {user_input}")
        print("─" * 50)
        
        try:
            # 显示协作步骤
            print("🔄 启动多代理协作...")
            print("   📋 意图解析代理 → 解析查询意图")
            
            # 执行查询但隐藏详细日志
            result = await self.team.query_with_collaboration(user_input, show_process=False)
            
            print("   🌤️  天气查询代理 → 获取天气数据")
            print("   ✨ 响应格式化代理 → 美化输出结果")
            print()
            
            # 显示最终结果
            print("📋 查询结果:")
            print("─" * 50)
            print(result)
            print("─" * 50)
            
        except Exception as e:
            print(f"❌ 查询失败: {e}")
        
        print()
    
    async def interactive_mode(self):
        """交互式查询模式"""
        await self.initialize()
        
        print("🌤️  欢迎使用智能天气查询系统")
        print("💡 支持查询：今天/明天/未来几天的天气")
        print("💡 支持城市：北京、上海、广州等37个主要城市")
        print("💡 输入 'exit' 或 'quit' 退出系统")
        print("═" * 60)
        print()
        
        while True:
            try:
                user_input = input("🌟 请输入天气查询: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['exit', 'quit', '退出', 'q']:
                    print("👋 感谢使用，再见！")
                    break
                
                await self.query_weather(user_input)
                
            except KeyboardInterrupt:
                print("\n👋 感谢使用，再见！")
                break
            except Exception as e:
                print(f"❌ 发生错误: {e}")
                print()
    
    async def demo_mode(self):
        """演示模式"""
        await self.initialize()
        
        print("🎭 天气查询演示模式")
        print("═" * 60)
        print()
        
        demo_queries = [
            "今天天气怎么样？",
            "上海明天天气",
            "广州未来3天天气"
        ]
        
        for i, query in enumerate(demo_queries, 1):
            print(f"📋 演示 {i}/{len(demo_queries)}")
            await self.query_weather(query)
            
            if i < len(demo_queries):
                print("⏳ 准备下一个演示...")
                await asyncio.sleep(2)
                print()
        
        print("🎉 演示完成！")
    
    async def close(self):
        """关闭系统"""
        if self.team:
            await self.team.close()

async def main():
    """主函数"""
    cli = SimpleWeatherCLI()
    
    try:
        # 检查命令行参数
        if len(sys.argv) > 1:
            if sys.argv[1] == "--demo":
                await cli.demo_mode()
            else:
                # 直接查询模式
                query = " ".join(sys.argv[1:])
                await cli.initialize()
                await cli.query_weather(query)
        else:
            # 交互式模式
            await cli.interactive_mode()
            
    finally:
        await cli.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 感谢使用，再见！")
    except Exception as e:
        print(f"❌ 系统错误: {e}")