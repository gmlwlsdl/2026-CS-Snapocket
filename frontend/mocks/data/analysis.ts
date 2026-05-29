import type { MockDocument } from './documents';

export interface AnalysisJob {
  jobId: string;
  documentId: string;
  startedAt: Date;
}

export const activeAnalysisJobs = new Map<string, AnalysisJob>();

export function buildAnalysisResult(doc: MockDocument) {
  return {
    id: doc.id,
    title: doc.title,
    category: doc.category,
    capture_date: doc.capture_date,
    summary: doc.summary,
    tags: doc.tags,
    raw_text: doc.raw_text,
    key_concepts: doc.key_concepts,
    deadline: doc.deadline,
    file_type: doc.file_type,
    file_url: doc.file_url,
  };
}

export function generateAnalysisForNewDoc(doc: MockDocument) {
  const categoryLabels: Record<string, string> = {
    lecture: '강의 내용 요약',
    assignment: '과제 요구사항 분석',
    notice: '공지 핵심 정보',
    receipt: '구매 내역 추출',
    memo: '메모 핵심 정리',
  };

  return {
    id: doc.id,
    title: doc.title || '제목 없는 문서',
    category: doc.category,
    capture_date: doc.capture_date,
    summary: `${categoryLabels[doc.category] || '문서 요약'}: ${doc.title}. AI가 문서를 분석하여 핵심 내용을 추출하였습니다.`,
    tags: [doc.category, '자동분석'],
    raw_text: '(OCR 텍스트 추출 결과)',
    key_concepts: ['자동 추출된 핵심 개념'],
    deadline: null,
    file_type: doc.file_type,
    file_url: doc.file_url,
  };
}
