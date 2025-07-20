"""
智能文本分塊服務
提供更智能的文本處理策略，替代簡單的硬截斷
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """文本分塊策略"""
    SEMANTIC = "semantic"      # 語義分塊（按句子和段落）
    FIXED = "fixed"           # 固定長度分塊
    HYBRID = "hybrid"         # 混合策略
    ALERT_OPTIMIZED = "alert_optimized"  # 警報優化分塊


@dataclass
class TextChunk:
    """文本塊數據類"""
    content: str
    start_index: int
    end_index: int
    chunk_type: str
    priority: int = 1
    metadata: Optional[Dict[str, Any]] = None


class SmartTextChunker:
    """
    智能文本分塊器
    
    提供多種文本分塊策略，特別針對安全警報內容進行優化。
    替代簡單的硬截斷，確保重要信息不會丟失。
    """
    
    def __init__(self, max_chunk_size: int = 8000, overlap_size: int = 200):
        """
        初始化文本分塊器
        
        Args:
            max_chunk_size: 最大塊大小（字符數）
            overlap_size: 塊間重疊大小（字符數）
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
        # 警報相關的關鍵詞模式
        self.alert_keywords = [
            r'規則描述[:：]\s*(.+)',
            r'警報等級[:：]\s*(\d+)',
            r'主機名稱[:：]\s*(.+)',
            r'規則 ID[:：]\s*(.+)',
            r'srcip[:：]\s*(.+)',
            r'dstip[:：]\s*(.+)',
            r'protocol[:：]\s*(.+)',
            r'user[:：]\s*(.+)',
            r'command[:：]\s*(.+)',
            r'url[:：]\s*(.+)',
        ]
        
        # 句子分隔符
        self.sentence_delimiters = r'[.!?。！？]\s+'
        
        # 段落分隔符
        self.paragraph_delimiters = r'\n\s*\n'
        
    def chunk_text(self, text: str, strategy: ChunkingStrategy = ChunkingStrategy.ALERT_OPTIMIZED) -> List[TextChunk]:
        """
        根據指定策略分塊文本
        
        Args:
            text: 要分塊的文本
            strategy: 分塊策略
            
        Returns:
            TextChunk 列表
        """
        if not text or not text.strip():
            return []
            
        text = text.strip()
        
        if strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunking(text)
        elif strategy == ChunkingStrategy.FIXED:
            return self._fixed_chunking(text)
        elif strategy == ChunkingStrategy.HYBRID:
            return self._hybrid_chunking(text)
        elif strategy == ChunkingStrategy.ALERT_OPTIMIZED:
            return self._alert_optimized_chunking(text)
        else:
            raise ValueError(f"不支持的分塊策略: {strategy}")
    
    def _semantic_chunking(self, text: str) -> List[TextChunk]:
        """
        語義分塊：按句子和段落進行智能分塊
        """
        chunks = []
        
        # 首先按段落分割
        paragraphs = re.split(self.paragraph_delimiters, text)
        
        current_chunk = ""
        start_index = 0
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            # 如果當前塊加上新段落超過限制，先保存當前塊
            if len(current_chunk) + len(paragraph) > self.max_chunk_size and current_chunk:
                chunks.append(TextChunk(
                    content=current_chunk.strip(),
                    start_index=start_index,
                    end_index=start_index + len(current_chunk),
                    chunk_type="semantic_paragraph"
                ))
                start_index += len(current_chunk) - self.overlap_size
                current_chunk = paragraph + "\n\n"
            else:
                current_chunk += paragraph + "\n\n"
        
        # 處理最後一個塊
        if current_chunk.strip():
            chunks.append(TextChunk(
                content=current_chunk.strip(),
                start_index=start_index,
                end_index=start_index + len(current_chunk),
                chunk_type="semantic_paragraph"
            ))
        
        return chunks
    
    def _fixed_chunking(self, text: str) -> List[TextChunk]:
        """
        固定長度分塊：按固定大小分割，保持重疊
        """
        chunks = []
        text_length = len(text)
        
        for i in range(0, text_length, self.max_chunk_size - self.overlap_size):
            end_index = min(i + self.max_chunk_size, text_length)
            chunk_content = text[i:end_index]
            
            chunks.append(TextChunk(
                content=chunk_content,
                start_index=i,
                end_index=end_index,
                chunk_type="fixed_length"
            ))
            
            if end_index >= text_length:
                break
        
        return chunks
    
    def _hybrid_chunking(self, text: str) -> List[TextChunk]:
        """
        混合分塊：結合語義和固定長度策略
        """
        # 首先嘗試語義分塊
        semantic_chunks = self._semantic_chunking(text)
        
        # 如果語義分塊結果太大，進一步分割
        final_chunks = []
        for chunk in semantic_chunks:
            if len(chunk.content) <= self.max_chunk_size:
                final_chunks.append(chunk)
            else:
                # 對大塊進行固定長度分割
                sub_chunks = self._fixed_chunking(chunk.content)
                for sub_chunk in sub_chunks:
                    final_chunks.append(TextChunk(
                        content=sub_chunk.content,
                        start_index=chunk.start_index + sub_chunk.start_index,
                        end_index=chunk.start_index + sub_chunk.end_index,
                        chunk_type="hybrid"
                    ))
        
        return final_chunks
    
    def _alert_optimized_chunking(self, text: str) -> List[TextChunk]:
        """
        警報優化分塊：專門針對安全警報內容優化
        
        優先保留關鍵信息，如規則描述、IP地址、用戶名等
        """
        # 分析文本中的關鍵信息
        key_info = self._extract_key_information(text)
        
        # 如果文本不長，直接返回
        if len(text) <= self.max_chunk_size:
            return [TextChunk(
                content=text,
                start_index=0,
                end_index=len(text),
                chunk_type="alert_optimized",
                priority=1,
                metadata={"key_info": key_info}
            )]
        
        # 按分隔符分割文本
        parts = re.split(r'\s*\|\s*', text)
        
        # 重新組裝，確保關鍵信息優先
        prioritized_parts = self._prioritize_alert_parts(parts, key_info)
        
        chunks = []
        current_chunk = ""
        start_index = 0
        
        for part in prioritized_parts:
            if len(current_chunk) + len(part) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(TextChunk(
                        content=current_chunk.strip(),
                        start_index=start_index,
                        end_index=start_index + len(current_chunk),
                        chunk_type="alert_optimized",
                        priority=1
                    ))
                    start_index += len(current_chunk) - self.overlap_size
                    current_chunk = part + " | "
                else:
                    # 單個部分就超過限制，強制分割
                    sub_chunks = self._fixed_chunking(part)
                    for sub_chunk in sub_chunks:
                        chunks.append(TextChunk(
                            content=sub_chunk.content,
                            start_index=start_index + sub_chunk.start_index,
                            end_index=start_index + sub_chunk.end_index,
                            chunk_type="alert_forced_split",
                            priority=2
                        ))
                    start_index += len(part)
            else:
                current_chunk += part + " | "
        
        # 處理最後一個塊
        if current_chunk.strip():
            chunks.append(TextChunk(
                content=current_chunk.strip().rstrip(" |"),
                start_index=start_index,
                end_index=start_index + len(current_chunk),
                chunk_type="alert_optimized",
                priority=1
            ))
        
        return chunks
    
    def _extract_key_information(self, text: str) -> Dict[str, Any]:
        """
        提取文本中的關鍵信息
        """
        key_info = {}
        
        for pattern in self.alert_keywords:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                key_name = pattern.split(r'[:：]')[0].strip()
                key_info[key_name] = matches
        
        return key_info
    
    def _prioritize_alert_parts(self, parts: List[str], key_info: Dict[str, Any]) -> List[str]:
        """
        根據重要性對警報部分進行排序
        """
        # 定義重要性順序
        priority_order = [
            "規則描述",
            "警報等級", 
            "主機名稱",
            "規則 ID",
            "srcip",
            "dstip",
            "protocol",
            "user",
            "command",
            "url"
        ]
        
        # 為每個部分分配優先級
        prioritized = []
        for part in parts:
            priority = 999  # 默認低優先級
            for i, key in enumerate(priority_order):
                if key.lower() in part.lower():
                    priority = i
                    break
            prioritized.append((priority, part))
        
        # 按優先級排序
        prioritized.sort(key=lambda x: x[0])
        
        return [part for _, part in prioritized]
    
    def get_optimal_chunk(self, text: str) -> str:
        """
        獲取最優的單個文本塊（用於單次向量化）
        
        優先保留最重要的信息，適合用於查詢向量化
        """
        if len(text) <= self.max_chunk_size:
            return text
        
        # 使用警報優化策略
        chunks = self._alert_optimized_chunking(text)
        
        if not chunks:
            return text[:self.max_chunk_size]
        
        # 返回優先級最高的塊
        best_chunk = min(chunks, key=lambda x: x.priority)
        return best_chunk.content
    
    def merge_chunks(self, chunks: List[TextChunk]) -> str:
        """
        合併多個文本塊
        """
        if not chunks:
            return ""
        
        # 按起始位置排序
        sorted_chunks = sorted(chunks, key=lambda x: x.start_index)
        
        # 合併內容，處理重疊
        merged_content = ""
        for i, chunk in enumerate(sorted_chunks):
            if i == 0:
                merged_content = chunk.content
            else:
                # 檢查重疊
                overlap = self._find_overlap(merged_content, chunk.content)
                if overlap:
                    merged_content += chunk.content[len(overlap):]
                else:
                    merged_content += " " + chunk.content
        
        return merged_content
    
    def _find_overlap(self, text1: str, text2: str) -> str:
        """
        找到兩個文本的重疊部分
        """
        min_overlap = 10  # 最小重疊長度
        
        for i in range(min(len(text1), len(text2)), min_overlap - 1, -1):
            if text1[-i:] == text2[:i]:
                return text1[-i:]
        
        return ""


# 便捷函數
def smart_chunk_text(text: str, max_size: int = 8000, strategy: ChunkingStrategy = ChunkingStrategy.ALERT_OPTIMIZED) -> List[str]:
    """
    便捷函數：智能分塊文本
    
    Args:
        text: 要分塊的文本
        max_size: 最大塊大小
        strategy: 分塊策略
        
    Returns:
        文本塊列表
    """
    chunker = SmartTextChunker(max_chunk_size=max_size)
    chunks = chunker.chunk_text(text, strategy)
    return [chunk.content for chunk in chunks]


def get_optimal_text(text: str, max_size: int = 8000) -> str:
    """
    便捷函數：獲取最優文本（用於單次向量化）
    
    Args:
        text: 原始文本
        max_size: 最大大小
        
    Returns:
        優化後的文本
    """
    chunker = SmartTextChunker(max_chunk_size=max_size)
    return chunker.get_optimal_chunk(text) 