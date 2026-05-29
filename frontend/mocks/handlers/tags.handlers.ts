import { http, HttpResponse } from 'msw';
import { MOCK_TAGS } from '../data/tags';
import { documentStore } from './documents.handlers';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

export const tagsHandlers = [
  // 태그 목록 조회
  http.get('/api/tags', ({ request }) => {
    const url = new URL(request.url);
    const keyword = url.searchParams.get('keyword')?.toLowerCase() ?? '';
    const tags = keyword
      ? MOCK_TAGS.filter((t) => t.name.toLowerCase().includes(keyword))
      : MOCK_TAGS;
    return ok(tags);
  }),

  // 문서 태그 추가
  http.post('/api/documents/:id/tags', async ({ params, request }) => {
    const doc = documentStore.get(params.id as string);
    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    const { tags } = await request.json() as { tags: string[] };
    const merged = Array.from(new Set([...doc.tags, ...tags]));
    documentStore.set(doc.id, { ...doc, tags: merged });
    return ok(merged.map((name, i) => ({ id: `tag-added-${i}`, name })));
  }),

  // 문서 태그 교체
  http.patch('/api/documents/:id/tags', async ({ params, request }) => {
    const doc = documentStore.get(params.id as string);
    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    const { tags } = await request.json() as { tags: string[] };
    documentStore.set(doc.id, { ...doc, tags });
    return ok(tags.map((name, i) => ({ id: `tag-replaced-${i}`, name })));
  }),

  // 태그 단건 삭제
  http.delete('/api/documents/:id/tags/:tagId', async ({ params }) => {
    const doc = documentStore.get(params.id as string);
    if (!doc) {
      return HttpResponse.json({ success: false, message: '문서를 찾을 수 없습니다.', data: null }, { status: 404 });
    }
    const tagName = MOCK_TAGS.find((t) => t.id === params.tagId)?.name;
    if (tagName) {
      documentStore.set(doc.id, { ...doc, tags: doc.tags.filter((t) => t !== tagName) });
    }
    return ok(null, '태그가 삭제되었습니다.');
  }),
];
