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
        # Vision model for seeing
        self.vision_llm = ChatOllama(model=config.VISION_MODEL, temperature=0.1)
        # Writer model for thinking and writing
        self.writer_llm = ChatOllama(model=config.TEXT_MODEL, temperature=0.7)
        
        self.pc = Pinecone(api_key=config.PINECONE_API_KEY)
        self.index = self.pc.Index(config.PINECONE_INDEX_NAME)

    def optimize_keyword(self, raw_text):
            """
            利用 LLM 将原本的口语化痛点，转化为“高搜索价值”的关键词组合
            """
            print(f"🧠 正在优化搜索词: {raw_text} ...")
            
            prompt = f"""
            你是一个小红书SEO专家。你的任务是将用户的“身体痛点描述”转化为“高效搜索关键词”。

            【原始描述】
            {raw_text}

            【优化规则】
            1. 必须保留地域词“澳洲”。
            2. 将口语转化为搜索术语（例如：“睡不醒” -> “嗜睡”，“没力气” -> “慢性疲劳”）。
            3. 组合应简洁，通常为 2-3 个词，中间用空格隔开。
            4. 这是一个搜索框输入，不要带任何标点符号。

            【输出示例】
            输入：澳洲 总是 觉得 累
            输出：澳洲 慢性疲劳 恢复

            输入：澳洲 关节 卡住
            输出：澳洲 关节僵硬 缓解

            【你的输出】
            (仅输出优化后的关键词字符串，不要包含任何解释或标签)
            """

            try:
                # 使用 writer_llm (Qwen/Llama) 进行快速转换
                resp = self.writer_llm.invoke([HumanMessage(content=prompt)])
                print("kw优化: ", resp)
                # 清理结果 (去掉可能的 <think> 标签，去掉引号)
                result = resp.content
                result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
                result = result.replace('"', '').replace("'", "").replace("。", "").strip()
                
                # 兜底：如果模型输出为空，还是用原词
                return result if result else raw_text

            except Exception as e:
                print(f"❌ 关键词优化失败: {e}")
                return raw_text # 失败时回退到原始词

    def extract_json(self, text):
        """
        🔥 Robust JSON Extraction
        """
        text = text.strip()
        data = {}

        # 1. Extract should_like
        like_match = re.search(r'"should_like"\s*:\s*(true|false)', text, re.IGNORECASE)
        data['should_like'] = True if like_match and like_match.group(1).lower() == 'true' else False

        # 2. Extract should_comment
        comment_match = re.search(r'"should_comment"\s*:\s*(true|false)', text, re.IGNORECASE)
        data['should_comment'] = True if comment_match and comment_match.group(1).lower() == 'true' else False

        # 3. Extract image_desc
        desc_match = re.search(r'"image_desc"\s*:\s*"(.*?)"\s*,\s*"image_kw"', text, re.DOTALL)
        if desc_match:
            data['image_desc'] = desc_match.group(1)
        else:
            start = text.find('"image_desc":')
            if start != -1:
                data['image_desc'] = text[start+14 : start+100] 
            else:
                data['image_desc'] = "无法解析描述"

        # 4. Extract image_kw
        kw_match = re.search(r'"image_kw"\s*:\s*"(.*?)"', text, re.DOTALL)
        data['image_kw'] = kw_match.group(1) if kw_match else "#无标签"
        
        # 5. Extract choice_index
        choice_match = re.search(r'"choice_index"\s*:\s*(\d+)', text)
        data['choice_index'] = int(choice_match.group(1)) if choice_match else 1

        return data

    def _search_pinecone(self, keywords):
        """Internal helper: Search Knowledge Base"""
        try:
            results = self.index.search(
                namespace=config.PINECONE_NAMESPACE, 
                query={"inputs": {"text": keywords}, "top_k": 2},
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
            
            # print(f"🧠 [知识库上下文]: {product_context_str.strip()}")
            return product_context_str, matched_products_list

        except Exception as e:
            print(f"⚠️ Pinecone 搜索失败: {e}")
            return "知识库连接失败，请进行通用回复。", []

    def _build_prompt(self, product_context_str):
        """Internal helper: Build System Prompt with CoT Instructions"""
        return f"""
        Lurky 澳洲生活（官方账号｜澳洲本地品牌｜XHS 评论自动化）

        你是澳洲本地健康品牌 Lurky 的【官方账号】，账号名为「Lurky 澳洲生活」。
        
        # --- 核心指令：显式思考 (Chain of Thought) ---
        **你必须先进行思考，然后再生成最终评论。**
        **请务必将你的思考过程包裹在 <think> 和 </think> 标签中。**
        
        在 <think> 标签内，你需要：
        1. 分析图片描述中的用户痛点或场景。
        2. 检查【关联产品库信息】中是否有相关的健康机制（Metabolism, Inflammation等）。
        3. 构思如何将产品逻辑转化为“生活观察”或“轻专业知识”，确保去营销化。
        4. 检查是否触犯了“禁止词”或“强营销”规则。
        
        思考结束后，在标签外输出最终的 JSON 或 纯文本评论。
        # ---------------------------------------------

        # --- 核心输入数据 ---
        【品牌/产品核心知识库 (Context)】
        {product_context_str}
        # -------------------

        【语言与地域规则】
        - 搜索：只使用中文关键词；每个搜索词必须包含“澳洲”
        - 评论：只用中文；评论文本中不出现“澳洲/城市名/州名”

        【评论对象限制】
        - 语境属于澳洲生活
        - 主题与生活健康相关
        - 非强卖货/非明显带货

        【知识库转化指令】
        1. **原理泛化**：将“产品含有X成分解决Y问题” -> “从机理上看，Y问题往往和X层面的代谢有关”。
        2. **隐形植入**：不提产品名，只提**生理机制**。
        3. **逻辑支撑**：利用科学解释作为“轻专业视角”。

        【输出格式】
        - 12–35 个中文字符
        - 1–3 行
        - 只包含评论文本

        【禁止词】
        官方权威/建议大家/必须/一定要/推荐购买/效果保证/立刻见效/神药/剂量数字/产品名/品牌名
        """

    def write_comment(self, image_desc, image_kw):
        """Legacy method: Generate comment (Non-streaming)"""
        try:
            context_str, matched_list = self._search_pinecone(image_kw)
            system_prompt = self._build_prompt(context_str)
            
            resp = self.writer_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"帖子图片分析报告：{image_desc}\n\n请生成一条评论：")
            ])
            
            # Use regex to remove <think> tags if they exist in legacy mode
            clean_text = re.sub(r'<think>.*?</think>', '', resp.content, flags=re.DOTALL).strip()
            comment_text = clean_text.replace('"', '').replace("'", "")
            
            return comment_text, matched_list

        except Exception as e:
            print(f"❌ 评论生成逻辑出错: {e}")
            return "看起来很不错！👍", []

    def write_comment_stream(self, image_desc, image_kw):
        """
        🔥 Streaming generation with CoT (Chain of Thought)
        Now explicitly requests <think> tags via prompt logic.
        """
        try:
            context_str, _ = self._search_pinecone(image_kw)
            system_prompt = self._build_prompt(context_str)

            # Stream response
            for chunk in self.writer_llm.stream([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"帖子图片分析报告：{image_desc}\n\n请生成一条评论（记得先输出 <think> 思考过程）：")
            ]):
                yield chunk.content

        except Exception as e:
            print(f"❌ 流式生成出错: {e}")
            yield "赞！👍"

    def see_and_decide(self, image_path):
        print(f"👀 {config.VISION_MODEL} 正在分析帖子详情...")
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        
        prompt = """
        Analyze this image for a social media bot. 
        Output STRICT JSON format only.

        # 任务 1: 分析内容 (存入 'image_desc')
        用一段中文简要描述图片内容。
        重点识别：【品类】(如鱼油、护肝片)、【核心成分】(如Omega-3、奶蓟草)、【适用人群】以及【品牌名】(如果可见)。

        # 任务 2: 生成标签 (存入 'image_kw')
        生成一组中文标签，用空格分隔。多生成通用成分词。

        # 任务 3: 决定是否互动 (存入 'should_comment')
        与【保健品、营养、健康饮食、运动、护肤】相关则为 true。

        # Output JSON Format:
        {
            "should_like": true,
            "should_comment": true,
            "image_desc": "描述...",
            "image_kw": "#标签"
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

        prompt = """
        Look at the search result grid.
        Identify the most relevant post cover image.
        Return JSON ONLY: { "choice_index": 1 }
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