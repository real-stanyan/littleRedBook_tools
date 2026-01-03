import base64
import json
import re
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from pinecone import Pinecone
import config

class DualAIAgent:
    def __init__(self):
        print(f"🔧 初始化双模型引擎...")
        self.vision_llm = ChatOllama(model=config.VISION_MODEL, temperature=0.1)
        self.writer_llm = ChatOllama(model=config.TEXT_MODEL, temperature=0.7)
        
        self.pc = Pinecone(api_key=config.PINECONE_API_KEY)
        self.index = self.pc.Index(config.PINECONE_INDEX_NAME)

    def extract_json(self, text):
        """
        🔥 超强容错版 JSON 提取：不依赖 json.loads，使用正则暴力提取核心字段
        解决模型输出 "image_desc": "包含"引号"的内容" 导致的解析错误
        """
        text = text.strip()
        data = {}

        # 1. 暴力提取 should_like (找 true/false)
        like_match = re.search(r'"should_like"\s*:\s*(true|false)', text, re.IGNORECASE)
        data['should_like'] = True if like_match and like_match.group(1).lower() == 'true' else False

        # 2. 暴力提取 should_comment
        comment_match = re.search(r'"should_comment"\s*:\s*(true|false)', text, re.IGNORECASE)
        data['should_comment'] = True if comment_match and comment_match.group(1).lower() == 'true' else False

        # 3. 暴力提取 image_desc (获取冒号后到下一个字段前的所有内容)
        # 这种写法比 json 库容错率高 100 倍
        desc_match = re.search(r'"image_desc"\s*:\s*"(.*?)"\s*,\s*"image_kw"', text, re.DOTALL)
        if desc_match:
            data['image_desc'] = desc_match.group(1)
        else:
            # 备用方案：如果正则没匹配到，尝试截取
            start = text.find('"image_desc":')
            if start != -1:
                data['image_desc'] = text[start+14 : start+100] # 截取一段作为描述
            else:
                data['image_desc'] = "无法解析描述"

        # 4. 暴力提取 image_kw
        kw_match = re.search(r'"image_kw"\s*:\s*"(.*?)"', text, re.DOTALL)
        data['image_kw'] = kw_match.group(1) if kw_match else "#无标签"
        
        # 5. 提取 choice_index (用于选贴)
        choice_match = re.search(r'"choice_index"\s*:\s*(\d+)', text)
        data['choice_index'] = int(choice_match.group(1)) if choice_match else 1

        return data
    def write_comment(self, image_desc, image_kw):
        """生成评论，强制返回元组 (str, list)，防止 NoneType 崩溃"""
        try:
            results = self.index.search(
                namespace=config.PINECONE_NAMESPACE, 
                query={"inputs": {"text": image_kw}, "top_k": 2},
                fields=["text"]
            )
            
            raw_hits = results.get('result', {}).get('hits', [])
            clean_hits = [h.to_dict() if hasattr(h, 'to_dict') else dict(h) for h in raw_hits]
            
            product_context_str = ""
            matched_products_list = [] 
            
            if clean_hits:
                for i, hit in enumerate(clean_hits):
                    text_content = hit.get('fields', {}).get('text', '')
                    matched_products_list.append(text_content)
                    product_context_str += f"\n[关联产品库信息 {i+1}]: {text_content}\n"
            else:
                product_context_str = "暂无具体产品关联信息。"

            print(f"🧠 [知识库上下文]: {product_context_str}")

            # 假设 product_context_str 已经在外部定义好了

            system_prompt = f"""
            Lurky 澳洲生活（官方账号｜澳洲本地品牌｜XHS 评论自动化）

            你是澳洲本地健康品牌 Lurky 的【官方账号】，账号名为「Lurky 澳洲生活」。

            你不是“公告发布号”，不是“促销销售号”，也不是“客服回复号”。
            你的角色是：以官方身份参与公开讨论，输出克制的观察与讨论视角，建立长期信任与品牌专业形象。

            # --- 核心输入数据 ---
            【品牌/产品核心知识库 (Context)】
            请仔细阅读并内化以下信息，将其作为你判断健康逻辑的底层依据，但**严禁直接复制原文**：
            {product_context_str}
            # -------------------

            【语言与地域规则】
            - 搜索：只使用中文关键词；每个搜索词必须包含“澳洲”（用于锁定澳洲华人内容池）
            - 评论：只用中文；评论文本中不出现“澳洲/城市名/州名”等定位词（避免刻意定位感）

            【评论对象限制｜Pre-filter】仅对以下内容生成评论，否则跳过：
            - 内容语境属于澳洲生活（通过“澳洲”搜索锁定 + 帖子文本/话题/地点/评论区语境确认）
            - 且主题与生活健康相关：状态、困扰、习惯、恢复、炎症、心血管、血脂、关节、疲劳等
            - 且非强卖货/非明显带货/非测评对比

            【知识库转化指令 (关键)】
            你要利用上方【知识库】中的成分原理、健康机制或品牌理念，来支撑你的评论，但必须经过“去营销化”处理：
            1. **原理泛化**：将“产品含有X成分能解决Y问题” 转化为 -> “从机理上看，Y问题往往和X层面的代谢有关”。
            2. **隐形植入**：不要提产品名，不要提具体的独家技术名，只提**通用的生理机制**。
            3. **逻辑支撑**：当用户提到某种困扰时，利用知识库中的科学解释作为你“轻专业视角”的来源。

            【禁止评论】
            - 强营销/带货/导购（链接、折扣码、私信、进群、团购等）
            - 医疗诊断、治疗建议、处方级建议
            - 情绪对立/争议性话题（引战）
            - **严禁提及知识库中的具体产品名称或型号**

            【评论目标】
            - 不卖货、不引导购买、不提品牌名/产品名
            - 不给具体剂量/周期
            - 不做权威口吻，不“教育”别人
            - 只参与讨论：短句、克制、留白

            【评论比例】
            60% 生活观察（A1）：共情澳洲生活场景，确认用户的状态。
            30% 轻专业视角（A2）：**调用知识库逻辑**，指出常被忽视的生理机制或健康关联。
            10% 留白判断（A3，且不可连续）：简短的总结或感叹。

            【输出格式】
            - 12–35 个中文字符
            - 1–3 行
            - 每条只表达 1 个点
            - 输出只包含评论文本本身（不要附加说明）

            【禁止词】
            官方权威/建议大家/必须/一定要/推荐购买/效果保证/立刻见效/神药/剂量数字/产品名/品牌名/原文引用

            【允许高频表达（自然官方语感｜替换旧模板表达）】
            实际交流中会遇到、现实情况里经常出现、在很多讨论里会提到、这个现象并不少见、
            日常交流中常被提及、从实践层面来看、从经验反馈来看、在实际应用中、
            一部分人会关注到、有些使用者会发现、部分人群会遇到、常见的疑问之一是、
            这个点容易被跳过、往往不会第一时间注意到、很容易被当成背景因素、容易被低估其影响

            【表达结构】
            观察 → 判断 (基于知识库逻辑) → 留白（不展开原理，不讲一大段）
            """

            resp = self.writer_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"帖子图片分析报告：{image_desc}\n\n请生成一条评论：")
            ])
            comment_text = resp.content.strip().replace('"', '').replace("'", "")
            
            # ✅ 成功路径：返回元组
            return comment_text, matched_products_list

        except Exception as e:
            print(f"❌ 评论生成逻辑出错: {e}")
            # ✅ 失败路径：必须返回元组，不能返回 None 或 string
            return "看起来很不错！👍", []
    def see_and_decide(self, image_path):
        print(f"👀 {config.VISION_MODEL} 正在分析帖子详情...")
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        # 🟢 优化后的 Prompt：去除了所有具象的品牌示例，防止模型产生偏见
        prompt = """
        Analyze this image for a social media bot. 
        Output STRICT JSON format only.

        # 任务 1: 分析内容 (存入 'image_desc')
        用一段中文简要描述图片内容。
        重点识别：【品类】(如鱼油、护肝片)、【核心成分】(如Omega-3、奶蓟草)、【适用人群】以及【品牌名】(如果可见)。
        直接输出纯文本描述，不要使用表格。

        # 任务 2: 生成标签 (存入 'image_kw')
        生成一组中文标签，用空格分隔。
        **重要策略**：为了匹配数据库，请多生成【通用成分词】和【功能词】，少生成冷门品牌词。
        (正确示例: "#深海鱼油 #Omega3 #心血管健康 #DHA")
        (错误示例: "#某某冷门品牌 #好物分享")

        # 任务 3: 决定是否互动 (存入 'should_comment')
        如果图片与【保健品、营养、健康饮食、运动、护肤】相关，必须设置为 true。
        积极参与互动，不要因为图片质量差就拒绝。
        (如果 should_comment 为 true，则 should_like 也必须为 true)

        # Output JSON Format:
        {
            "should_like": true,
            "should_comment": true,
            "image_desc": "在此处填入根据图片实际分析得到的中文描述文本...",
            "image_kw": "#标签1 #标签2 #标签3"
        }
        """
        
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_b64}"}
        ])
        
        try:
            resp = self.vision_llm.invoke([msg])
            return self.extract_json(resp.content)
        except Exception as e:
            print(f"❌ 详情页分析失败: {e}")
            return None
    def choose_feed_post(self, feed_image_path):
        print(f"🔎 {config.VISION_MODEL} 正在浏览搜索列表...")
        with open(feed_image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # 🟢 修复后的提示词：简化指令，中英夹杂模型理解最好
        prompt = """
        Look at the search result grid (2 columns).
        Identify the most relevant post cover image.
        
        Positions:
        1: Top Left
        2: Top Right
        3: Bottom Left
        4: Bottom Right
        
        Return JSON ONLY:
        {
            "choice_index": 1
        }
        """
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_b64}"}
        ])
        
        try:
            resp = self.vision_llm.invoke([msg])
            data = self.extract_json(resp.content)
            return data.get("choice_index", 1) if data else 1
        except Exception as e:
            print(f"❌ 选贴分析失败: {e}, 默认选 1")
            return 1