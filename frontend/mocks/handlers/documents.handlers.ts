import { http, HttpResponse } from 'msw';
import { MOCK_DOCUMENTS_MAP, MOCK_DOCUMENTS_INITIAL, type MockDocument } from '../data/documents';

const store = new Map<string, MockDocument>(
  MOCK_DOCUMENTS_INITIAL.map((d) => [d.id, { ...d }])
);

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

const MOCK_PLACEHOLDER_PNG = Uint8Array.from(
  atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQAABjE+ibYAAAAASUVORK5CYII='),
  (c) => c.charCodeAt(0)
);

export { store as documentStore };

export const documentsHandlers = [
  // 목록 조회
  http.get('/api/documents', ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') ?? '1');
    const size = parseInt(url.searchParams.get('size') ?? '20');
    const keyword = url.searchParams.get('keyword')?.toLowerCase() ?? '';
    const category = url.searchParams.get('category') ?? '';
    const status = url.searchParams.get('status') ?? '';
    const startDate = url.searchParams.get('start_date') ?? '';
    const endDate = url.searchParams.get('end_date') ?? '';
    const sort = url.searchParams.get('sort') ?? 'created_at_desc';

    let docs = Array.from(store.values());

    if (keyword) {
      docs = docs.filter(
        (d) =>
          d.title.toLowerCase().includes(keyword) ||
          d.summary.toLowerCase().includes(keyword) ||
          d.tags.some((t) => t.toLowerCase().includes(keyword))
      );
    }
    if (category) docs = docs.filter((d) => d.category === category);
    if (status) docs = docs.filter((d) => d.status === status);
    if (startDate) docs = docs.filter((d) => d.capture_date && d.capture_date >= startDate);
    if (endDate) docs = docs.filter((d) => d.capture_date && d.capture_date <= endDate);

    if (sort === 'created_at_asc') {
      docs.sort((a, b) => a.created_at.localeCompare(b.created_at));
    } else {
      docs.sort((a, b) => b.created_at.localeCompare(a.created_at));
    }

    const total = docs.length;
    const offset = (page - 1) * size;
    const items = docs.slice(offset, offset + size).map((d) => ({
      id: d.id,
      title: d.title,
      category: d.category,
      status: d.status,
      file_type: d.file_type,
      tags: d.tags,
      capture_date: d.capture_date,
      created_at: d.created_at,
    }));

    return ok({
      items,
      pagination: {
        page,
        size,
        total,
        has_next: offset + size < total,
      },
    });
  }),

  // 단건 조회
  http.get('/api/documents/:id', ({ params }) => {
    const doc = store.get(params.id as string);
    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    return ok(doc);
  }),

  // 업로드
  http.post('/api/documents/upload', async ({ request }) => {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;
    const autoAnalyze = formData.get('autoAnalyze') === 'true';
    const now = new Date().toISOString();
    const id = `doc-upload-${Date.now()}`;
    const fileType = file?.type?.startsWith('audio/') ? 'audio' : 'image';

    const newDoc: MockDocument = {
      id,
      title: file?.name?.replace(/\.[^.]+$/, '') ?? '새 문서',
      category: 'memo',
      capture_date: now.slice(0, 10),
      summary: '',
      tags: [],
      key_concepts: [],
      raw_text: '',
      file_url: `data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Crect width='800' height='600' fill='%23e5e7eb'/%3E%3Ctext x='400' y='300' text-anchor='middle' fill='%236b7280' font-family='sans-serif' font-size='24'%3E${encodeURIComponent(file?.name ?? '업로드된 파일')}%3C/text%3E%3C/svg%3E`,
      file_type: fileType as 'image' | 'audio',
      status: autoAnalyze ? 'processing' : 'uploaded',
      deadline: null,
      created_at: now,
    };

    store.set(id, newDoc);

    return ok({
      document_id: id,
      file_url: newDoc.file_url,
      file_type: newDoc.file_type,
      status: newDoc.status,
    });
  }),

  // 수정
  http.patch('/api/documents/:id', async ({ params, request }) => {
    const doc = store.get(params.id as string);
    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    const body = await request.json() as Partial<MockDocument>;
    const updated = { ...doc, ...body };
    store.set(doc.id, updated);
    return ok(updated);
  }),

  // 삭제
  http.delete('/api/documents/:id', ({ params }) => {
    const exists = store.has(params.id as string);
    if (!exists) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    store.delete(params.id as string);
    return ok(null, '문서가 삭제되었습니다.');
  }),

  // 파일 바이너리 (이미지/오디오 미리보기)
  http.get('/api/documents/:id/file', () => {
    return new HttpResponse(MOCK_PLACEHOLDER_PNG, {
      headers: { 'Content-Type': 'image/png' },
    });
  }),
];
