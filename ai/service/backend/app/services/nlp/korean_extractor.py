"""후처리에서 사용하는 한국어 형태소 분석 유틸."""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# 카테고리 fallback 점수 계산에 사용하는 문서 유형 키워드 사전
_DOC_KEYWORDS: dict[str, list[str]] = {
    "notice":   ["공지", "안내", "신청", "마감", "기간", "일정", "모집", "공고"],
    "lecture":  ["강의", "수업", "과제", "시험", "출석", "주차", "교수", "학점", "수강"],
    "receipt":  ["합계", "총액", "결제", "카드", "승인", "부가세", "vat", "영수증"],
    "invoice":  ["세금계산서", "공급가액", "청구서", "거래처", "사업자번호", "부가세", "공급자"],
    "contract": ["계약서", "계약", "갑", "을", "서명", "날인", "계약기간", "위약금"],
    "resume":   ["이력서", "경력사항", "학력", "자기소개서", "지원동기", "취득자격"],
    "form":     ["신청서", "신청인", "작성일", "서식", "양식", "기재", "작성자"],
    "report":   ["보고서", "분석", "결론", "요약", "연구", "검토", "현황", "방안"],
}


def classify_doc_type_enhanced(text: str) -> str:
    """문서 유형별 키워드 출현 점수를 계산해 최고 점수 타입을 반환한다."""
    lowered = text.lower()
    scores: dict[str, int] = {}
    for doc_type, keywords in _DOC_KEYWORDS.items():
        scores[doc_type] = sum(lowered.count(kw) for kw in keywords)
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "unknown"


class KoreanExtractor:
    """kiwipiepy 기반 한국어 명사 추출기."""

    def __init__(self) -> None:
        self._kiwi = None
        self._load_kiwi()

    def _load_kiwi(self) -> None:
        try:
            from kiwipiepy import Kiwi
            self._kiwi = Kiwi()
        except ImportError:
            logger.warning("kiwipiepy not installed; falling back to regex tokenizer")

    def extract_nouns(self, text: str) -> list[str]:
        # 모델이 없는 환경에서도 후처리가 깨지지 않게 정규식 토크나이저로 폴백한다.
        if self._kiwi is None:
            tokens = re.findall(r"[가-힣]{2,}", text)
            return [w for w, _ in Counter(tokens).most_common(20)]

        results = self._kiwi.analyze(text)
        nouns: list[str] = []
        for token in results[0][0]:
            if token.tag in ("NNG", "NNP") and len(token.form) >= 2:
                nouns.append(token.form)
        return [w for w, _ in Counter(nouns).most_common(20)]
