#!/usr/bin/env python3
"""
彩云天气 MCP 服务器
基于 Anthropic MCP Python SDK 实现真实天气查询
"""

import asyncio
import httpx
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

# 加载环境变量 - 按优先级加载，从上级目录查找
import os
parent_dir = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(parent_dir, ".env.local"))  # 优先加载本地配置
load_dotenv(os.path.join(parent_dir, ".env"))  # 兜底加载默认配置

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp-server")

# 创建服务器实例
server = Server("weather-mcp-server")

# 彩云天气 API 配置
CAIYUN_API_KEY = os.getenv("CAIYUN_API_KEY")
if not CAIYUN_API_KEY:
    logger.error("❌ 未设置 CAIYUN_API_KEY 环境变量，请在 .env 文件中配置")
    raise ValueError("CAIYUN_API_KEY 环境变量未设置")

CAIYUN_BASE_URL = os.getenv("CAIYUN_BASE_URL", "https://api.caiyunapp.com/v2.6")

# 高德地图 API 配置
AMAP_API_KEY = os.getenv("AMAP_API_KEY")
if not AMAP_API_KEY:
    logger.error("❌ 未设置 AMAP_API_KEY 环境变量，请在 .env 文件中配置")
    raise ValueError("AMAP_API_KEY 环境变量未设置")

AMAP_BASE_URL = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com/v3/geocode/geo")

# 城市坐标映射
CITY_COORDINATES = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "南京": (32.0603, 118.7969),
    "武汉": (30.5928, 114.3055),
    "成都": (30.5728, 104.0668),
    "西安": (34.3416, 108.9398),
    "重庆": (29.5630, 106.5516),
    "天津": (39.3434, 117.3616),
    "苏州": (31.2989, 120.5853),
    "青岛": (36.0671, 120.3826),
    "宁波": (29.8683, 121.5440),
    "无锡": (31.5912, 120.3019),
    "济南": (36.6512, 117.1201),
    "大连": (38.9140, 121.6147),
    "沈阳": (41.8057, 123.4315),
    "长春": (43.8171, 125.3235),
    "哈尔滨": (45.8038, 126.5349),
    "福州": (26.0745, 119.2965),
    "厦门": (24.4798, 118.0894),
    "昆明": (25.0389, 102.7183),
    "南昌": (28.6820, 115.8581),
    "合肥": (31.8669, 117.2741),
    "石家庄": (38.0428, 114.5149),
    "太原": (37.8706, 112.5489),
    "郑州": (34.7466, 113.6254),
    "长沙": (28.2282, 112.9388),
    "南宁": (22.8170, 108.3669),
    "海口": (20.0444, 110.1999),
    "贵阳": (26.6470, 106.6302),
    "兰州": (36.0611, 103.8343),
    "银川": (38.4681, 106.2731),
    "西宁": (36.6171, 101.7782),
    "乌鲁木齐": (43.7793, 87.6177),
    "拉萨": (29.6625, 91.1110)
}

# 天气现象映射
SKYCON_MAP = {
    "CLEAR_DAY": "晴天",
    "CLEAR_NIGHT": "晴夜",
    "PARTLY_CLOUDY_DAY": "多云",
    "PARTLY_CLOUDY_NIGHT": "多云",
    "CLOUDY": "阴天",
    "LIGHT_HAZE": "轻度雾霾",
    "MODERATE_HAZE": "中度雾霾",
    "HEAVY_HAZE": "重度雾霾",
    "LIGHT_RAIN": "小雨",
    "MODERATE_RAIN": "中雨",
    "HEAVY_RAIN": "大雨",
    "STORM_RAIN": "暴雨",
    "FOG": "雾",
    "LIGHT_SNOW": "小雪",
    "MODERATE_SNOW": "中雪",
    "HEAVY_SNOW": "大雪",
    "STORM_SNOW": "暴雪",
    "DUST": "浮尘",
    "SAND": "沙尘",
    "WIND": "大风"
}

class AmapGeocoder:
    """高德地图地理编码客户端"""
    
    def __init__(self):
        self.api_key = AMAP_API_KEY
        self.base_url = AMAP_BASE_URL
        # 坐标缓存，避免重复API调用
        self.coord_cache = {}
    
    async def close(self):
        """兼容性方法 - 高德API使用上下文管理器，无需手动关闭"""
        pass
    
    async def get_coordinates(self, city_name: str) -> Optional[tuple[float, float]]:
        """获取城市坐标，优先使用缓存和预定义坐标"""
        # 1. 优先使用预定义的精确坐标
        if city_name in CITY_COORDINATES:
            return CITY_COORDINATES[city_name]
        
        # 2. 检查缓存
        if city_name in self.coord_cache:
            return self.coord_cache[city_name]
        
        # 3. 调用高德地理编码API - 使用上下文管理器，每次创建新客户端
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {
                    "key": self.api_key,
                    "address": city_name,
                    "output": "json"
                }
                
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if data.get("status") == "1" and data.get("count", "0") != "0":
                    geocodes = data.get("geocodes", [])
                    if geocodes:
                        location = geocodes[0].get("location", "")
                        if location:
                            # 解析经纬度 "116.480881,39.989410"
                            lon, lat = map(float, location.split(","))
                            coordinates = (lat, lon)  # 注意：我们存储为(纬度,经度)
                            
                            # 缓存结果
                            self.coord_cache[city_name] = coordinates
                            logger.info(f"✅ 获取城市坐标成功：{city_name} -> {coordinates}")
                            return coordinates
            
            logger.warning(f"⚠️ 未找到城市坐标：{city_name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 地理编码API调用失败：{city_name}, 错误：{e}")
            return None

class WeatherAPI:
    """彩云天气API客户端"""
    
    def __init__(self):
        self.api_key = CAIYUN_API_KEY
        self.base_url = CAIYUN_BASE_URL
    
    async def close(self):
        """兼容性方法 - 彩云天气API使用上下文管理器，无需手动关闭"""
        pass
    
    async def get_coordinates(self, city: str) -> Optional[tuple[float, float]]:
        """获取城市坐标，动态调用高德地理编码"""
        return await amap_geocoder.get_coordinates(city)
    
    async def get_daily_weather(self, city: str, days: int = 1) -> Dict[str, Any]:
        """获取天气预报"""
        coordinates = await self.get_coordinates(city)
        if not coordinates:
            raise ValueError(f"不支持的城市：{city}")
        
        lat, lon = coordinates
        url = f"{self.base_url}/{self.api_key}/{lon},{lat}/daily"
        params = {"dailysteps": min(days, 15)}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            if e.response.status_code == 429:
                raise Exception(f"API调用频率过高，请稍后再试。彩云天气API有频率限制。")
            else:
                raise Exception(f"天气API请求失败: {e}")
        except Exception as e:
            raise Exception(f"天气API调用错误: {e}")
    
    
    def format_weather_data(self, data: Dict[str, Any], city: str, target_day: int = 0) -> str:
        """格式化天气数据"""
        if data.get("status") != "ok":
            return f"❌ 获取{city}天气失败"
        
        daily = data["result"]["daily"]
        
        if target_day >= len(daily["temperature"]):
            return f"❌ 没有{city}第{target_day+1}天的天气数据"
        
        # 获取指定天的数据
        date_info = daily["temperature"][target_day]
        date = date_info["date"][:10]  # 取日期部分
        
        # 温度信息
        temp = daily["temperature"][target_day]
        temp_max = int(temp["max"])
        temp_min = int(temp["min"])
        
        # 天气现象
        skycon = daily["skycon"][target_day]["value"]
        weather_desc = SKYCON_MAP.get(skycon, skycon)
        
        # 降水概率
        precipitation = daily["precipitation"][target_day]
        rain_prob = int(precipitation["probability"] * 100)
        
        # 湿度
        humidity = daily["humidity"][target_day]
        humidity_avg = int(humidity["avg"] * 100)
        
        # 风速
        wind = daily["wind"][target_day]
        wind_speed = wind["avg"]["speed"]
        wind_level = self.wind_speed_to_level(wind_speed)
        
        # 生活建议
        tips = self._get_weather_tips(weather_desc, temp_max, temp_min, rain_prob)
        
        return f"""📍 {city} {date}
🌤️ 天气：{weather_desc}
🌡️ 温度：{temp_min}°C ~ {temp_max}°C
💧 湿度：{humidity_avg}%
💨 风力：{wind_level}级
🌧️ 降水概率：{rain_prob}%
💡 生活建议：{tips}"""
    
    def wind_speed_to_level(self, speed_ms: float) -> int:
        """风速转风力等级"""
        speed_kmh = speed_ms * 3.6
        if speed_kmh < 1:
            return 0
        elif speed_kmh < 6:
            return 1
        elif speed_kmh < 12:
            return 2
        elif speed_kmh < 20:
            return 3
        elif speed_kmh < 29:
            return 4
        elif speed_kmh < 39:
            return 5
        elif speed_kmh < 50:
            return 6
        elif speed_kmh < 62:
            return 7
        elif speed_kmh < 75:
            return 8
        elif speed_kmh < 89:
            return 9
        elif speed_kmh < 103:
            return 10
        elif speed_kmh < 118:
            return 11
        else:
            return 12
    
    def _get_weather_tips(self, weather: str, temp_max: int, temp_min: int, rain_prob: int) -> str:
        """根据天气生成生活建议"""
        tips = []
        
        # 温度建议
        if temp_max >= 30:
            tips.append("天气炎热，注意防暑降温")
        elif temp_min <= 5:
            tips.append("天气寒冷，注意保暖添衣")
        elif temp_max - temp_min > 15:
            tips.append("昼夜温差大，适时增减衣物")
        
        # 降水建议
        if rain_prob > 70:
            tips.append("降雨概率高，建议携带雨具")
        elif rain_prob > 30:
            tips.append("可能有降雨，备好雨伞")
        
        # 天气现象建议
        if "雾" in weather or "霾" in weather:
            tips.append("能见度较低，出行注意安全")
        elif "晴" in weather:
            tips.append("天气晴朗，适合户外活动")
        elif "雪" in weather:
            tips.append("有降雪，注意路面湿滑")
        
        return "，".join(tips) if tips else "天气适宜，祝您生活愉快"

# 全局API实例
amap_geocoder = AmapGeocoder()
weather_api = WeatherAPI()

# ============= 工具处理函数 =============

async def handle_query_weather_today(arguments: dict) -> List[TextContent]:
    """查询今天的天气"""
    city = arguments.get("city", "北京")
    try:
        data = await weather_api.get_daily_weather(city, days=1)
        result = weather_api.format_weather_data(data, city, target_day=0)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        logger.error(f"查询今天天气失败: {e}")
        return [TextContent(type="text", text=f"❌ 查询{city}今天天气失败: {str(e)}")]

async def handle_query_weather_tomorrow(arguments: dict) -> List[TextContent]:
    """查询明天的天气"""
    city = arguments.get("city", "北京")
    try:
        data = await weather_api.get_daily_weather(city, days=2)
        if len(data["result"]["daily"]["temperature"]) > 1:
            result = weather_api.format_weather_data(data, city, target_day=1)
            return [TextContent(type="text", text=result)]
        else:
            return [TextContent(type="text", text=f"❌ 获取{city}明天天气数据不足")]
    except Exception as e:
        logger.error(f"查询明天天气失败: {e}")
        return [TextContent(type="text", text=f"❌ 查询{city}明天天气失败: {str(e)}")]

async def handle_query_weather_future_days(arguments: dict) -> List[TextContent]:
    """查询未来几天的天气预报"""
    city = arguments.get("city", "北京")
    days = arguments.get("days", 3)
    try:
        data = await weather_api.get_daily_weather(city, days=days)
        
        if data.get("status") != "ok":
            return [TextContent(type="text", text=f"❌ 获取{city}天气失败")]
        
        daily = data["result"]["daily"]
        results = [f"📍 {city} 未来{days}天天气预报："]
        
        for i in range(min(days, len(daily["temperature"]))):
            date_info = daily["temperature"][i]
            date = date_info["date"][:10]
            
            temp_max = int(date_info["max"])
            temp_min = int(date_info["min"])
            
            skycon = daily["skycon"][i]["value"]
            weather_desc = SKYCON_MAP.get(skycon, skycon)
            
            results.append(f"📅 {date}：{weather_desc}，{temp_min}°C ~ {temp_max}°C")
        
        return [TextContent(type="text", text="\n".join(results))]
        
    except Exception as e:
        logger.error(f"查询未来天气失败: {e}")
        return [TextContent(type="text", text=f"❌ 查询{city}未来{days}天天气失败: {str(e)}")]

async def handle_get_supported_cities(arguments: dict) -> List[TextContent]:
    """获取支持的城市列表"""
    cities = list(CITY_COORDINATES.keys())
    cities_text = "内置城市列表：\n" + "、".join(cities) + "\n\n其他城市也支持，通过高德地图API动态获取坐标。"
    return [TextContent(type="text", text=cities_text)]

async def handle_get_city_coordinates(arguments: dict) -> List[TextContent]:
    """获取城市坐标"""
    city = arguments.get("city", "北京")
    try:
        coordinates = await amap_geocoder.get_coordinates(city)
        if coordinates:
            lat, lon = coordinates
            result = f"📍 {city} 坐标信息：\n纬度：{lat}\n经度：{lon}\n坐标：{lat},{lon}"
            return [TextContent(type="text", text=result)]
        else:
            return [TextContent(type="text", text=f"❌ 未找到城市：{city}，请检查城市名称是否正确")]
    except Exception as e:
        logger.error(f"获取城市坐标失败: {e}")
        return [TextContent(type="text", text=f"❌ 获取{city}坐标失败: {str(e)}")]

# ============= 工具映射表 =============

TOOL_HANDLERS: Dict[str, Callable] = {
    "query_weather_today": handle_query_weather_today,
    "query_weather_tomorrow": handle_query_weather_tomorrow,
    "query_weather_future_days": handle_query_weather_future_days,
    "get_supported_cities": handle_get_supported_cities,
    "get_city_coordinates": handle_get_city_coordinates,
}

@server.list_tools()
async def list_tools() -> list[Tool]:
    """返回可用工具列表"""
    return [
        Tool(
            name="query_weather_today",
            description="查询今天的天气",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、广州等",
                        "default": "北京"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query_weather_tomorrow",
            description="查询明天的天气",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、广州等",
                        "default": "北京"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query_weather_future_days",
            description="查询未来几天的天气预报",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、广州等",
                        "default": "北京"
                    },
                    "days": {
                        "type": "integer",
                        "description": "查询天数，范围1-15天",
                        "minimum": 1,
                        "maximum": 15,
                        "default": 3
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_supported_cities",
            description="获取支持的城市列表",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_city_coordinates",
            description="获取城市坐标（支持全国所有城市）",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，支持全国所有城市，如：北京、上海、三亚、拉萨等",
                        "default": "北京"
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用"""
    # 获取对应的处理函数
    handler = TOOL_HANDLERS.get(name)
    
    if not handler:
        return [TextContent(type="text", text=f"未知工具: {name}")]
    
    try:
        # 直接调用处理函数
        return await handler(arguments)
    except Exception as e:
        logger.error(f"工具调用失败: {name}, 错误: {str(e)}")
        return [TextContent(type="text", text=f"工具执行失败: {str(e)}")]

async def main():
    """主函数"""
    logger.info("启动彩云天气 MCP 服务器...")
    try:
        async with stdio_server() as streams:
            await server.run(
                streams[0], streams[1],
                server.create_initialization_options()
            )
    finally:
        await weather_api.close()
        await amap_geocoder.close()

if __name__ == "__main__":
    asyncio.run(main())