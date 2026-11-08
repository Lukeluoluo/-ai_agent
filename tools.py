# tools.py
import os
import json
import httpx
import asyncio
import uuid
import re
from typing import Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain_community.tools.tavily_search import TavilySearchResults
from dotenv import load_dotenv

load_dotenv()

# ---------------- 配置区 ----------------
AMAP_KEY = os.getenv("AMAP_API_KEY")
QWEATHER_KEY = os.getenv("QWEATHER_API_KEY")
QWEATHER_HOST = os.getenv("QWEATHER_HOST")
TUNIU_API_KEY = os.getenv("TUNIU_API_KEY")

AMAP_SEMAPHORE = asyncio.Semaphore(3)
TUNIU_BASE = "https://openapi.tuniu.cn/mcp"

class AmapAPIError(Exception):
    pass

# ==========================================
# 途牛 MCP 通用请求封装
# ==========================================
async def _call_tuniu_mcp(service: str, tool_name: str, arguments: dict) -> dict:
    if not TUNIU_API_KEY:
        return {"error": "未配置 TUNIU_API_KEY，请在 .env 文件中设置。"}
    url = f"{TUNIU_BASE}/{service}"
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "apiKey": TUNIU_API_KEY}
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp_text = resp.text
            if resp.status_code != 200: return {"error": f"HTTP {resp.status_code}: {resp_text[:100]}"}
            if "text/event-stream" in resp.headers.get("content-type", ""):
                match = re.search(r'data:\s*(\{.*\})', resp_text, re.DOTALL)
                if match: resp_text = match.group(1)
            data = json.loads(resp_text)
            if "error" in data:
                return {"error": f"途牛错误: {data['error'].get('message', '未知')}"}
            result = data.get("result", {})
            content_list = result.get("content", [])
            if content_list and content_list[0].get("type") == "text":
                text = content_list[0]["text"]
                try: return json.loads(text)
                except: return {"raw_text": text}
            return result
    except Exception as e:
        return {"error": f"请求异常: {str(e)}"}

# ==========================================
# 途牛 6 大实时报价工具
# ==========================================
class TuniuHotelInput(BaseModel):
    cityName: str = Field(description="城市名")
    checkin: str = Field(description="入住 YYYY-MM-DD")
    checkout: str = Field(description="离店 YYYY-MM-DD")
    keyword: str = Field(description="关键词", default="")
class TuniuHotelSearchTool(BaseTool):
    name: str = "search_hotels_realtime"
    description: str = "途牛实时酒店报价"
    args_schema: Type[BaseModel] = TuniuHotelInput
    async def _arun(self, cityName: str, checkin: str, checkout: str, keyword: str = "") -> str:
        args = {"cityName": cityName, "checkin": checkin, "checkout": checkout}
        if keyword: args["keyword"] = keyword
        return json.dumps(await _call_tuniu_mcp("hotel", "tuniuHotelSearch", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class TuniuFlightInput(BaseModel):
    departureCityName: str = Field(description="出发城市")
    arrivalCityName: str = Field(description="到达城市")
    departureDate: str = Field(description="日期 YYYY-MM-DD")
class TuniuFlightSearchTool(BaseTool):
    name: str = "search_flights_realtime"
    description: str = "途牛实时国内机票"
    args_schema: Type[BaseModel] = TuniuFlightInput
    async def _arun(self, departureCityName: str, arrivalCityName: str, departureDate: str) -> str:
        args = {"departureCityName": departureCityName, "arrivalCityName": arrivalCityName, "departureDate": departureDate}
        return json.dumps(await _call_tuniu_mcp("flight", "searchLowestPriceFlight", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class TuniuIntlFlightInput(BaseModel):
    departure_city: str = Field(description="出发城市")
    arrival_city: str = Field(description="到达城市")
    departure_date: str = Field(description="日期 YYYY-MM-DD")
class TuniuIntlFlightSearchTool(BaseTool):
    name: str = "search_intl_flights_realtime"
    description: str = "途牛实时国际机票"
    args_schema: Type[BaseModel] = TuniuIntlFlightInput
    async def _arun(self, departure_city: str, arrival_city: str, departure_date: str) -> str:
        args = {"departure_city": departure_city, "arrival_city": arrival_city, "departure_date": departure_date}
        return json.dumps(await _call_tuniu_mcp("intel_flight", "list_intel_flights", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class TuniuTicketInput(BaseModel):
    scenic_name: str = Field(description="景点名称")
    depart_date: str = Field(description="日期 YYYY-MM-DD", default="")
class TuniuTicketSearchTool(BaseTool):
    name: str = "search_tickets_realtime"
    description: str = "途牛实时门票起价"
    args_schema: Type[BaseModel] = TuniuTicketInput
    async def _arun(self, scenic_name: str, depart_date: str = "") -> str:
        args = {"scenic_name": scenic_name}
        if depart_date: args["depart_date"] = depart_date
        return json.dumps(await _call_tuniu_mcp("ticket", "query_cheapest_tickets", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class TuniuTrainInput(BaseModel):
    departureCityName: str = Field(description="出发城市")
    arrivalCityName: str = Field(description="到达城市")
    departureDate: str = Field(description="日期 YYYY-MM-DD")
class TuniuTrainSearchTool(BaseTool):
    name: str = "search_trains_realtime"
    description: str = "途牛实时火车票"
    args_schema: Type[BaseModel] = TuniuTrainInput
    async def _arun(self, departureCityName: str, arrivalCityName: str, departureDate: str) -> str:
        args = {"departureCityName": departureCityName, "arrivalCityName": arrivalCityName, "departureDate": departureDate}
        return json.dumps(await _call_tuniu_mcp("train", "searchLowestPriceTrain", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class TuniuCruiseInput(BaseModel):
    departsDateBegin: str = Field(description="起始日 YYYY-MM-DD")
    departsDateEnd: str = Field(description="结束日 YYYY-MM-DD")
class TuniuCruiseSearchTool(BaseTool):
    name: str = "search_cruises_realtime"
    description: str = "途牛邮轮查询"
    args_schema: Type[BaseModel] = TuniuCruiseInput
    async def _arun(self, departsDateBegin: str, departsDateEnd: str) -> str:
        args = {"departsDateBegin": departsDateBegin, "departsDateEnd": departsDateEnd}
        return json.dumps(await _call_tuniu_mcp("cruise", "searchCruiseList", args), ensure_ascii=False)
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

# ==========================================
# 基础兜底工具
# ==========================================
async def _call_amap_api(endpoint: str, params: dict) -> dict:
    if not AMAP_KEY: raise AmapAPIError("未配置 AMAP_API_KEY")
    params["key"] = AMAP_KEY
    url = f"https://restapi.amap.com/v3/{endpoint}"
    async with AMAP_SEMAPHORE:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    if data.get("status") != "1": raise AmapAPIError(f"高德 API 错误: {data.get('info')}")
    return data

class WeatherInput(BaseModel): location: str = Field(description="城市名称")
class RealWeatherTool(BaseTool):
    name: str = "get_weather"
    description: str = "未来 7 天天气"
    args_schema: Type[BaseModel] = WeatherInput
    async def _arun(self, location: str) -> str:
        try:
            url = f"https://{QWEATHER_HOST}/geo/v2/city/lookup"
            async with httpx.AsyncClient() as c:
                loc_data = (await c.get(url, params={"location": location, "key": QWEATHER_KEY})).json()
            loc_id = loc_data["location"][0]["id"]
            url = f"https://{QWEATHER_HOST}/v7/weather/7d"
            async with httpx.AsyncClient() as c:
                data = (await c.get(url, params={"location": loc_id, "key": QWEATHER_KEY})).json()
            res = {"city": location, "forecast": [{"date": d["fxDate"], "day_weather": d["textDay"], "max_temp": f"{d['tempMax']}℃", "min_temp": f"{d['tempMin']}℃", "precip": f"{d['precip']}mm"} for d in data["daily"]]}
            return json.dumps(res, ensure_ascii=False)
        except Exception as e: return f"天气查询失败: {e}"
    def _run(self, location: str) -> str: return asyncio.run(self._arun(location))

class PoiInput(BaseModel): keyword: str = Field(description="关键词"); city: str = Field(description="城市")
class RealPoiSearchTool(BaseTool):
    name: str = "search_map_poi"
    description: str = "高德搜地点(含经纬度)"
    args_schema: Type[BaseModel] = PoiInput
    async def _arun(self, keyword: str, city: str) -> str:
        try:
            data = await _call_amap_api("place/text", {"keywords": keyword, "city": city, "citylimit": "true", "extensions": "all"})
            return json.dumps({"results": [{"name": p["name"], "address": p["address"], "location": p["location"], "rating": p.get("biz_ext", {}).get("rating", "暂无")} for p in data.get("pois", [])[:5]]}, ensure_ascii=False)
        except Exception as e: return f"搜索失败: {e}"
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class HotelInput(BaseModel): city: str = Field(description="城市"); area: str = Field(description="区域", default="")
class RealHotelSearchTool(BaseTool):
    name: str = "search_hotels_basic"
    description: str = "高德搜酒店(含经纬度)"
    args_schema: Type[BaseModel] = HotelInput
    async def _arun(self, city: str, area: str = "") -> str:
        try:
            data = await _call_amap_api("place/text", {"keywords": f"{area} 酒店" if area else "酒店", "city": city, "types": "住宿服务"})
            return json.dumps({"results": [{"name": p["name"], "address": p["address"], "location": p["location"]} for p in data.get("pois", [])[:5]]}, ensure_ascii=False)
        except Exception as e: return f"搜索失败: {e}"
    def _run(self, **kwargs) -> str: return asyncio.run(self._arun(**kwargs))

class FlightInput(BaseModel): origin: str = Field(description="出发地"); destination: str = Field(description="目的地"); date: str = Field(description="日期")
class TavilyFlightSearchTool(BaseTool):
    name: str = "search_flights_basic"
    description: str = "航班兜底"
    args_schema: Type[BaseModel] = FlightInput
    def _run(self, origin: str, destination: str, date: str) -> str:
        try: return TavilySearchResults(max_results=3).run(f"{origin} 到 {destination} {date} 航班")
        except Exception as e: return f"失败: {e}"
    async def _arun(self, **kwargs) -> str: return self._run(**kwargs)

class ReviewInput(BaseModel): poi_name: str = Field(description="名称")
class RealReviewSearchTool(BaseTool):
    name: str = "get_reviews"
    description: str = "查全网差评"
    args_schema: Type[BaseModel] = ReviewInput
    def _run(self, poi_name: str) -> str:
        try: return TavilySearchResults(max_results=4).run(f"{poi_name} 评价 差评 避坑")
        except Exception as e: return f"失败: {e}"
    async def _arun(self, **kwargs) -> str: return self._run(**kwargs)

# ==========================================
# 核心：真实路线距离矩阵计算工具
# ==========================================
class DistanceMatrixInput(BaseModel):
    mode: str = Field(description="出行方式：'driving'(驾车), 'walking'(步行), 'transit'(公交)")
    locations: str = Field(description="地点列表：'名称1,经度1,纬度1|名称2,经度2,纬度2'")

class RealDistanceMatrixTool(BaseTool):
    name: str = "get_real_distance_matrix"
    description: str = "计算多个地点两两之间的真实驾车/公交/步行距离(km)和耗时(min)。"
    args_schema: Type[BaseModel] = DistanceMatrixInput

    async def _fetch(self, mode, o_lng, o_lat, d_lng, d_lat):
        url = f"https://restapi.amap.com/v3/direction/{mode}?origin={o_lng},{o_lat}&destination={d_lng},{d_lat}&key={AMAP_KEY}"
        if mode == "transit": url += "&city=全国"
        try:
            async with httpx.AsyncClient() as c:
                data = (await c.get(url, timeout=10.0)).json()
            if data.get("status") == "1" and data.get("route", {}).get("paths"):
                p = data["route"]["paths"][0]
                return {"distance": int(p["distance"])/1000, "duration": int(p["duration"])/60}
        except: pass
        return None

    def _run(self, mode: str, locations: str) -> str: return asyncio.run(self._arun(mode, locations))
    
    async def _arun(self, mode: str, locations: str) -> str:
        pts = [{"name": p.split(",")[0], "lng": p.split(",")[1], "lat": p.split(",")[2]} for p in locations.split("|") if len(p.split(",")) >= 3]
        if len(pts) < 2: return "至少需要两个地点。"

        tasks = [self._fetch(mode, pts[i]["lng"], pts[i]["lat"], pts[j]["lng"], pts[j]["lat"]) for i in range(len(pts)) for j in range(len(pts)) if i != j]
        res = await asyncio.gather(*tasks)
        
        matrix = []
        idx = 0
        for i in range(len(pts)):
            for j in range(len(pts)):
                if i != j:
                    r = res[idx]
                    if r: matrix.append(f"[{pts[i]['name']}] -> [{pts[j]['name']}]：{r['distance']:.1f} km，耗时 {r['duration']:.0f} 分钟")
                    else: matrix.append(f"[{pts[i]['name']}] -> [{pts[j]['name']}]：获取失败")
                    idx += 1
        return "📊 真实路线距离矩阵：\n" + "\n".join(matrix) + "\n\n💡 请根据上述真实耗时，重新调整行程顺序，确保不走回头路且符合时间窗。"

# ==========================================
# 工具列表导出
# ==========================================
LOCAL_TOOLS = [
    RealWeatherTool(),
    RealPoiSearchTool(),
    RealReviewSearchTool(),
    RealHotelSearchTool(),
    TavilyFlightSearchTool(),
    RealDistanceMatrixTool(),  # 👈 核心：真实路网计算
    TuniuHotelSearchTool(),
    TuniuFlightSearchTool(),
    TuniuIntlFlightSearchTool(),
    TuniuTicketSearchTool(),
    TuniuTrainSearchTool(),
    TuniuCruiseSearchTool(),
]