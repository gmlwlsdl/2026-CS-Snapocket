import { http, HttpResponse } from 'msw';
import { documentStore } from './documents.handlers';
import { activeAnalysisJobs, buildAnalysisResult, generateAnalysisForNewDoc } from '../data/analysis';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

const ANALYSIS_DELAY_MS = 4000;

export const analysisHandlers = [
  // 분석 시작
  http.post('/api/analysis/:documentId/start', ({ params }) => {
    const docId = params.documentId as string;
    const doc = documentStore.get(docId);

    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }

    const jobId = `job-${Date.now()}`;
    activeAnalysisJobs.set(docId, { jobId, documentId: docId, startedAt: new Date() });
    documentStore.set(docId, { ...doc, status: 'processing' });

    return ok({ job_id: jobId, status: 'processing' });
  }),

  // 분석 상태 조회
  http.get('/api/analysis/:documentId/status', ({ params }) => {
    const docId = params.documentId as string;
    const doc = documentStore.get(docId);

    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }

    const job = activeAnalysisJobs.get(docId);
    const now = Date.now();

    if (job && now - job.startedAt.getTime() >= ANALYSIS_DELAY_MS) {
      const finishedAt = new Date(job.startedAt.getTime() + ANALYSIS_DELAY_MS).toISOString();
      documentStore.set(docId, { ...doc, status: 'analyzed' });
      activeAnalysisJobs.delete(docId);

      return ok({
        status: 'analyzed',
        started_at: job.startedAt.toISOString(),
        finished_at: finishedAt,
      });
    }

    if (job) {
      return ok({
        status: 'processing',
        started_at: job.startedAt.toISOString(),
        finished_at: null,
      });
    }

    return ok({
      status: doc.status,
      started_at: null,
      finished_at: null,
    });
  }),

  // 분석 결과 조회
  http.get('/api/analysis/:documentId/result', ({ params }) => {
    const docId = params.documentId as string;
    const doc = documentStore.get(docId);

    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }

    if (doc.status !== 'analyzed') {
      return HttpResponse.json(
        { success: false, message: '분석이 완료되지 않았습니다.', data: null },
        { status: 422 }
      );
    }

    const result = doc.summary
      ? buildAnalysisResult(doc)
      : generateAnalysisForNewDoc(doc);

    return ok(result);
  }),

  // 분석 결과 확정
  http.post('/api/analysis/:documentId/confirm', async ({ params, request }) => {
    const docId = params.documentId as string;
    const doc = documentStore.get(docId);

    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }

    const body = await request.json() as {
      title: string;
      category: string;
      capture_date: string;
      deadline?: string | null;
      summary: string;
      tags: string[];
    };

    documentStore.set(docId, {
      ...doc,
      title: body.title,
      category: body.category,
      capture_date: body.capture_date,
      deadline: body.deadline ?? null,
      summary: body.summary,
      tags: body.tags,
      status: 'analyzed',
    });

    return ok(null, '분석 결과가 저장되었습니다.');
  }),

  // 재분석
  http.post('/api/analysis/:documentId/retry', ({ params }) => {
    const docId = params.documentId as string;
    const doc = documentStore.get(docId);

    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }

    const jobId = `job-retry-${Date.now()}`;
    activeAnalysisJobs.set(docId, { jobId, documentId: docId, startedAt: new Date() });
    documentStore.set(docId, { ...doc, status: 'processing' });

    return ok({ job_id: jobId, status: 'processing' });
  }),
];
