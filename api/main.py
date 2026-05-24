import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.factors.financial_factor import js_score, get_finance, normalize_code

app = FastAPI(title="财报评分API", version="1.0.0")

# 启动事件
@app.on_event("startup")
async def startup_event():
    load_stock_pool()

# 静态文件目录
STATIC_DIR = Path(__file__).parent.parent / "web"

# 加载股票池到内存
STOCK_POOL_FILE = Path(__file__).parent.parent / "stock_full_pool.csv"
stock_pool = []

def load_stock_pool():
    """加载股票池到内存"""
    global stock_pool
    try:
        if STOCK_POOL_FILE.exists():
            df = pd.read_csv(STOCK_POOL_FILE)
            stock_pool = df.to_dict('records')
            print(f"股票池加载完成，共 {len(stock_pool)} 只")
        else:
            print(f"股票池文件不存在: {STOCK_POOL_FILE}")
    except Exception as e:
        print(f"加载股票池失败: {e}")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 日志目录和文件
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "access.log"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StockCode(BaseModel):
    code: str


def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.client.host if request.client else "unknown"


def get_stock_name(code: str) -> str:
    """尝试获取股票名称"""
    try:
        import pandas as pd
        # 使用完整股票池
        pool_file = Path(__file__).parent.parent / "stock_full_pool.csv"
        if pool_file.exists():
            df = pd.read_csv(pool_file)
            df['code'] = df['code'].astype(str).str.zfill(6)
            match = df[df['code'] == code.zfill(6)]
            if not match.empty:
                return match.iloc[0]['name'].strip()
    except Exception:
        pass

    # 如果找不到，返回 "股票代码: xxxxxx"
    return f"股票代码:{code.zfill(6)}"


def calculate_quarter_scores(code: str, refresh: bool = False):
    """计算3个季度的评分，包括各分项和财务数据"""
    scores = {}
    finance_data = get_finance(code, refresh=refresh)

    # 获取最近几个季度的财务数据
    if finance_data is not None and not finance_data.empty:
        # 取最近3个季度
        recent_data = finance_data.tail(3).iloc[::-1]  # 翻转，最新的在最前面
    else:
        recent_data = None

    # ============================================================
    # p_flg 参数说明（因子层取数逻辑）：
    #   p_flg=1: 取最近3个季度数据(tail(3))用于计算"本季度"评分
    #   p_flg=2: 取上移1位的3个季度数据(iloc[-4:-1])用于计算"上季度"评分
    #   p_flg=0: 取上移2位的3个季度数据(iloc[-5:-2])用于计算"上上季度"评分
    #
    # 举例（假设数据按时间正序，最新在最后）：
    #   数据: [2024-06, 2024-09, 2024-12, 2025-03, 2025-06, 2025-09, 2025-12]
    #   p_flg=1 → [2025-06, 2025-09, 2025-12] → 评分对应2025-12报告期
    #   p_flg=2 → [2025-03, 2025-06, 2025-09] → 评分对应2025-09报告期
    #   p_flg=0 → [2024-12, 2025-03, 2025-06] → 评分对应2025-06报告期
    #
    # recent_data 索引说明：
    #   recent_data = df.tail(3).iloc[::-1] 翻转后，最新在前
    #   索引0=本季度(2025-12), 1=上季度(2025-09), 2=上上季度(2025-06)
    # ============================================================
    quarter_mapping = {
        '本季度': (1, 0),   # p_flg=1取最近3季, recent_data[0]=最新季度
        '上季度': (2, 1),   # p_flg=2取上移1位, recent_data[1]=上季度
        '上上季度': (0, 2)  # p_flg=0取上移2位, recent_data[2]=上上季度
    }
    for quarter_name in ['本季度', '上季度', '上上季度']:
        p_flg, data_idx = quarter_mapping[quarter_name]
        total, detail = js_score(code, p_flg=p_flg)
        quarter_info = {
            "total": total,
            "扣非": detail.get("扣非净利润", {}).get("total", 0),
            "归母": detail.get("归母净利润", {}).get("total", 0),
            "营收": detail.get("营业收入", {}).get("total", 0),
            "扣非趋势": detail.get("扣非净利润", {}).get("trend", 0),
            "归母趋势": detail.get("归母净利润", {}).get("trend", 0),
            "营收趋势": detail.get("营业收入", {}).get("trend", 0),
        }

        # 添加实际财务数据
        if recent_data is not None and len(recent_data) > data_idx:
            row = recent_data.iloc[data_idx]
            quarter_info["report_date"] = str(row['报告期'])
            quarter_info["财务数据"] = {
                "净利润": str(row['净利润']),
                "净利润同比": str(row['净利润同比增长率']),
                "扣非净利润": str(row['扣非净利润']),
                "扣非净利润同比": str(row['扣非净利润同比增长率']),
                "营业总收入": str(row['营业总收入']),
                "营业总收入同比": str(row['营业总收入同比增长率'])
            }

        scores[quarter_name] = quarter_info

    return scores


def analyze_trend(scores: dict) -> tuple:
    """分析趋势，返回趋势方向和详细解读"""
    current = scores['本季度']
    last = scores['上季度']
    last_last = scores['上上季度']

    # 分析每个指标的趋势
    koufei_trend = "持平" if current['扣非趋势'] == 0 else ("增长" if current['扣非趋势'] > 0 else "下滑")
    guimu_trend = "持平" if current['归母趋势'] == 0 else ("增长" if current['归母趋势'] > 0 else "下滑")
    yingshou_trend = "持平" if current['营收趋势'] == 0 else ("增长" if current['营收趋势'] > 0 else "下滑")

    # 总分趋势
    values = [last_last['total'], last['total'], current['total']]

    # 分析趋势方向
    if values[2] > values[1] > values[0]:
        trend = "up"
        text = "连续3个季度增长，增速加快"
    elif values[2] > values[1] and values[1] >= values[0]:
        trend = "up"
        text = "近2个季度持续增长"
    elif values[2] > values[1]:
        drop = values[2] - values[1]
        if drop >= 3:
            text = "本季度大幅回升"
        else:
            text = "本季度小幅回升"
        trend = "up"
    elif values[2] < values[1] < values[0]:
        trend = "down"
        text = "连续3个季度下滑，业绩承压"
    elif values[2] < values[1] and values[1] <= values[0]:
        trend = "down"
        text = "近2个季度持续下滑"
    elif values[2] < values[1]:
        drop = values[1] - values[2]
        if drop >= 5:
            text = f"本季度急剧下滑，跌幅{drop:.1f}分"
        elif drop >= 3:
            text = f"本季度大幅下滑，跌幅{drop:.1f}分"
        else:
            text = f"本季度小幅下滑，跌幅{drop:.1f}分"
        trend = "down"
    else:
        trend = "stable"
        text = "评分保持平稳"

    # 构建详细解读
    detail_parts = []

    # 扣非趋势
    if current['扣非'] > 5:
        detail_parts.append("扣非净利润表现优秀")
    elif current['扣非'] > 0:
        detail_parts.append("扣非净利润盈利")
    elif current['扣非'] > -2:
        detail_parts.append("扣非净利润小幅亏损")
    else:
        detail_parts.append("扣非净利润大幅下滑")

    # 营收趋势
    if current['营收'] > 3:
        detail_parts.append("营收快速增长")
    elif current['营收'] > 0:
        detail_parts.append("营收稳步增长")
    elif current['营收'] > -1:
        detail_parts.append("营收小幅下滑")
    else:
        detail_parts.append("营收明显下滑")

    # 趋势分解读
    if current['扣非趋势'] < -0.5 and current['归母趋势'] < -0.5:
        detail_parts.append("盈利趋势恶化")
    elif current['扣非趋势'] > 0.5 or current['归母趋势'] > 0.5:
        detail_parts.append("盈利趋势向好")

    detail_text = "，".join(detail_parts)

    return trend, text, detail_text


def analyze_single_quarter_trend(current: dict, prev: dict, prev_prev: dict) -> tuple:
    """分析单个季度的趋势，返回趋势方向和详细解读"""
    if not current:
        return "stable", "数据不足，无法分析"

    # 构建虚拟的3个季度数据用于分析
    if prev:
        values = [prev_prev.get('total', 0) if prev_prev else 0,
                  prev.get('total', 0),
                  current.get('total', 0)]
    else:
        values = [0, 0, current.get('total', 0)]

    # 分析趋势方向
    if len([v for v in values if v != 0]) < 2:
        trend = "stable"
        text = "数据不足，无法判断趋势"
    elif values[2] > values[1] > values[0]:
        trend = "up"
        text = "连续增长，增速加快"
    elif values[2] > values[1] and values[1] >= values[0]:
        trend = "up"
        text = "近2个季度持续增长"
    elif values[2] > values[1]:
        drop = values[2] - values[1]
        if drop >= 3:
            text = "本季度大幅回升"
        else:
            text = "本季度小幅回升"
        trend = "up"
    elif values[2] < values[1] < values[0]:
        trend = "down"
        text = "连续下滑，业绩承压"
    elif values[2] < values[1] and values[1] <= values[0]:
        trend = "down"
        text = "近2个季度持续下滑"
    elif values[2] < values[1]:
        drop = values[1] - values[2]
        if drop >= 5:
            text = f"本季度急剧下滑，跌幅{drop:.1f}分"
        elif drop >= 3:
            text = f"本季度大幅下滑，跌幅{drop:.1f}分"
        else:
            text = f"本季度小幅下滑，跌幅{drop:.1f}分"
        trend = "down"
    else:
        trend = "stable"
        text = "评分保持平稳"

    return trend, text


def analyze_quarter_trends(scores: dict) -> dict:
    """为每个季度生成独立的趋势分析"""
    quarter_trends = {}

    # 本季度的趋势（基于3个季度）
    trend, text = analyze_single_quarter_trend(
        scores.get('本季度'),
        scores.get('上季度'),
        scores.get('上上季度')
    )
    quarter_trends['本季度'] = {'trend': trend, 'trend_text': text}

    # 上季度的趋势（基于上上季度和上季度）
    trend, text = analyze_single_quarter_trend(
        scores.get('上季度'),
        scores.get('上上季度'),
        None
    )
    quarter_trends['上季度'] = {'trend': trend, 'trend_text': text}

    # 上上季度没有前期数据，标记为无法分析
    quarter_trends['上上季度'] = {'trend': 'stable', 'trend_text': '数据不足，无法分析'}

    return quarter_trends


def generate_all_quarter_insights(scores: dict) -> dict:
    """为每个季度生成独立的简要说明"""
    quarter_insights = {}

    # 本季度
    quarter_insights['本季度'] = generate_quarter_insights(scores.get('本季度', {}))

    # 上季度
    quarter_insights['上季度'] = generate_quarter_insights(scores.get('上季度', {}))

    # 上上季度
    quarter_insights['上上季度'] = generate_quarter_insights(scores.get('上上季度', {}))

    return quarter_insights


def generate_quarter_insights(current: dict) -> list:
    """为单个季度生成简要说明"""
    insights = []

    # 1. 综合评分
    if current['total'] >= 15:
        insights.append(f"综合评分{current['total']}分，表现优秀")
    elif current['total'] >= 10:
        insights.append(f"综合评分{current['total']}分，业绩良好")
    elif current['total'] >= 5:
        insights.append(f"综合评分{current['total']}分，业绩一般")
    elif current['total'] >= 0:
        insights.append(f"综合评分{current['total']}分，盈利较弱")
    elif current['total'] >= -3:
        insights.append(f"综合评分{current['total']}分，业绩下滑")
    else:
        insights.append(f"综合评分{current['total']}分，业绩承压")

    # 2. 扣非净利润评价
    if current.get('扣非', 0) > 5:
        insights.append(f"扣非净利润表现强劲，得{current['扣非']}分")
    elif current.get('扣非', 0) > 0:
        insights.append(f"扣非净利润盈利{current['扣非']}分，主营业务有利润")
    elif current.get('扣非', 0) > -2:
        insights.append(f"扣非净利润小幅亏损{current['扣非']}分，需关注")
    else:
        insights.append(f"扣非净利润大幅下滑{current['扣非']}分，盈利存疑")

    # 3. 营业收入评价
    if current.get('营收', 0) > 3:
        insights.append(f"营业收入增长明显，得{current['营收']}分，市场需求旺盛")
    elif current.get('营收', 0) > 0:
        insights.append(f"营业收入稳步增长{current['营收']}分，业务扩张中")
    elif current.get('营收', 0) > -1:
        insights.append(f"营业收入小幅下滑{current['营收']}分，基本持平")
    else:
        insights.append(f"营业收入下滑{current['营收']}分，市场需求萎缩")

    # 4. 归母净利润特殊情况
    if current.get('归母', 0) > 3 and current.get('扣非', 0) < 0:
        insights.append("归母净利润与扣非背离，需警惕非经常损益占比过高")
    elif current.get('归母', 0) < -2 and current.get('扣非', 0) > -1:
        insights.append("归母净利润下滑幅度大于扣非，关注少数股东权益变化")

    # 5. 投资建议
    if current['total'] < -3:
        insights.append("业绩下行风险较大，建议回避或减仓")
    elif current['total'] >= 10:
        insights.append("整体表现稳健，可保持关注或适度配置")
    elif current.get('扣非', 0) < -2:
        insights.append("主营业务盈利能力堪忧，需进一步观察")
    else:
        insights.append("建议持续关注基本面变化")

    return insights


@app.get("/")
async def root(request: Request):
    """首页 - 返回静态HTML"""
    # 判断是否是移动端
    user_agent = request.headers.get('user-agent', '').lower()
    is_mobile = 'mobile' in user_agent or 'android' in user_agent

    html_file = STATIC_DIR / "index_simple.html"
    if html_file.exists():
        return FileResponse(html_file)

    return {"message": "财报评分API", "version": "1.0.0"}


@app.get("/index.html")
async def index_html():
    """显式访问index.html"""
    html_file = STATIC_DIR / "index_simple.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"error": "File not found"}


@app.get("/api/v1/stock/search")
async def search_stock(q: str, limit: int = 10):
    """搜索股票，支持代码或名称模糊匹配"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"=== 搜索请求: q={repr(q)}, limit={limit}")
    
    if not q or len(q) < 2:
        logger.info(f"  返回空: q 长度不足")
        return []

    q_lower = q.lower().strip()
    results = []

    for stock in stock_pool:
        code = str(stock.get('code', ''))
        name = str(stock.get('name', '')).lower().replace(" ","")

        # 模糊匹配：代码包含 或 名称包含
        if q_lower in code or q_lower in name:
            result_code = str(stock.get('code', '')).zfill(6)
            result_name = stock.get('name')
            logger.info(f"  匹配到: code={repr(result_code)}, name={repr(result_name)}")
            results.append({
                'code': result_code,
                'name': result_name
            })
            if len(results) >= limit:
                break
    
    logger.info(f"  返回结果数: {len(results)}")
    return results


@app.get("/api/v1/financial/score/{code}")
async def get_financial_score(code: str, request: Request, refresh: bool = False):
    """获取单只股票3个季度评分"""
    client_ip = get_client_ip(request)
    code_normalized = normalize_code(code)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        stock_name = get_stock_name(code_normalized)
        scores = calculate_quarter_scores(code_normalized, refresh=refresh)
        quarter_trends = analyze_quarter_trends(scores)
        quarter_insights = generate_all_quarter_insights(scores)

        result = {
            "code": code_normalized,
            "name": stock_name,
            "scores": scores,
            "quarter_trends": quarter_trends,
            "quarter_insights": quarter_insights,
            "updated_at": datetime.now().strftime("%Y-%m-%d")
        }

        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | 成功")
        return result

    except Exception as e:
        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | 失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "code": code_normalized})


@app.get("/api/v1/financial/detail/{code}")
async def get_financial_detail(code: str, request: Request, refresh: bool = False):
    """获取财报详情（含历史数据）"""
    client_ip = get_client_ip(request)
    code_normalized = normalize_code(code)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        stock_name = get_stock_name(code_normalized)
        finance_data = get_finance(code_normalized, refresh=refresh)
        scores = calculate_quarter_scores(code_normalized, refresh=refresh)
        quarter_trends = analyze_quarter_trends(scores)
        quarter_insights = generate_all_quarter_insights(scores)

        # 将 DataFrame 转为 dict，并处理 NaN 值
        if finance_data is not None:
            finance_dict = finance_data.fillna("").to_dict(orient="records")
        else:
            finance_dict = None

        result = {
            "code": code_normalized,
            "name": stock_name,
            "scores": scores,
            "quarter_trends": quarter_trends,
            "quarter_insights": quarter_insights,
            "finance_data": finance_dict,
            "updated_at": datetime.now().strftime("%Y-%m-%d")
        }

        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | 详情查询成功")
        return result

    except Exception as e:
        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | 详情查询失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "code": code_normalized})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ========== K线接口 ==========
from src.datafactory.data_manager import get_kline_after_disclosure, normalize_code


@app.get("/api/v1/financial/kline/{code}")
async def get_financial_kline(code: str, quarter: str = "本季度", request: Request = None):
    """获取财报发布后7个交易日的K线数据

    参数:
    - code: 股票代码
    - quarter: 本季度/上季度/上上季度 (默认本季度)
    """
    client_ip = get_client_ip(request) if request else "unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    code_normalized = normalize_code(code)

    try:
        kline_data = get_kline_after_disclosure(code_normalized, quarter, days=7)

        # 检查是否有错误
        if kline_data.get("error"):
            return JSONResponse(
                status_code=404,
                content={
                    "error": kline_data.get("error"),
                    "code": code_normalized,
                    "quarter": quarter
                }
            )

        result = {
            "code": code_normalized,
            "quarter": quarter,
            "report_period": kline_data.get("报告期"),
            "disclosure_date": kline_data.get("公告日期"),
            "report_type": kline_data.get("类型"),
            "prev_close": kline_data.get("prev_close"),
            "kline": kline_data.get("kline", []),
            "updated_at": datetime.now().strftime("%Y-%m-%d")
        }

        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | K线查询成功: {quarter}")
        return result

    except Exception as e:
        logger.info(f"{timestamp} | {client_ip} | {code_normalized} | K线查询失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e), "code": code_normalized})


# 建议反馈 API
FEEDBACK_FILE = Path(__file__).parent.parent / "feedbacks.json"


class Feedback(BaseModel):
    content: str
    code: str = ""
    name: str = ""


@app.post("/api/v1/feedback")
async def submit_feedback(feedback: Feedback, request: Request):
    """提交建议反馈"""
    client_ip = get_client_ip(request)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 读取现有反馈
        feedbacks = []
        if FEEDBACK_FILE.exists():
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                feedbacks = json.load(f)

        # 添加新反馈
        new_feedback = {
            "id": len(feedbacks) + 1,
            "timestamp": timestamp,
            "ip": client_ip,
            "code": feedback.code,
            "name": feedback.name,
            "content": feedback.content,
            "status": "new"
        }
        feedbacks.append(new_feedback)

        # 保存到文件
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)

        logger.info(f"{timestamp} | {client_ip} | 建议提交成功: {feedback.content[:50]}...")
        return {"success": True, "message": "感谢您的反馈！"}

    except Exception as e:
        logger.info(f"{timestamp} | {client_ip} | 建议提交失败: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# 股票搜索API
@app.get("/api/v1/reports/search")
async def search_reports(q: str):
    """搜索股票（从今日报告中）"""
    import pandas as pd
    from datetime import datetime

    today_str = datetime.now().strftime("%Y%m%d")
    result_file = Path(__file__).parent.parent / "src" / "result" / f"batch_result_{today_str}.csv"

    if not result_file.exists():
        return []

    try:
        df = pd.read_csv(result_file)
        q_lower = q.lower().strip()
        # 模糊匹配
        matches = df[df['code'].astype(str).str.contains(q, na=False) |
                     df['name'].astype(str).str.lower().str.contains(q, na=False)]
        results = matches.head(10).to_dict('records')
        return results
    except Exception as e:
        return []


@app.get("/api/v1/reports/today")
async def get_today_reports():
    """获取今日多因子评分报告数据（从batch_result_YYYYMMDD.csv读取）"""
    from datetime import datetime
    today_str = datetime.now().strftime("%Y%m%d")
    result_file = Path(__file__).parent.parent / "src" / "result" / f"batch_result_{today_str}.csv"
    date_str = today_str

    # 如果今日文件不存在，查找最新可用文件
    if not result_file.exists():
        result_dir = Path(__file__).parent.parent / "src" / "result"
        csv_files = sorted(result_dir.glob("batch_result_*.csv"), reverse=True)
        if csv_files:
            result_file = csv_files[0]
            # 从文件名提取日期
            date_str = result_file.stem.replace("batch_result_", "")
        else:
            return JSONResponse(status_code=404, content={"error": f"无可用报告数据"})

    try:
        df = pd.read_csv(result_file)
        # 转为字典列表
        records = df.to_dict('records')
        return {
            "date": date_str,
            "count": len(records),
            "data": records
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/v1/reports/top")
async def get_reports_top(n: int = 10):
    """获取评分TOP N股票"""
    from datetime import datetime
    today_str = datetime.now().strftime("%Y%m%d")
    result_file = Path(__file__).parent.parent / "src" / "result" / f"batch_result_{today_str}.csv"

    if not result_file.exists():
        return JSONResponse(status_code=404, content={"error": f"今日({today_str})报告数据不存在"})

    try:
        df = pd.read_csv(result_file)
        df_sorted = df.sort_values('total_score', ascending=False).head(n)
        return {
            "date": today_str,
            "count": n,
            "data": df_sorted.to_dict('records')
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})