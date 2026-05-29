import { http, HttpResponse } from 'msw';
import { documentStore } from './documents.handlers';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

function scoreDoc(doc: ReturnType<typeof documentStore.get>, keyword: string) {
  if (!doc) return 0;
  const kw = keyword.toLowerCase();
  let score = 0;
  if (doc.title.toLowerCase().includes(kw)) score += 3;
  if (doc.summary.toLowerCase().includes(kw)) score += 2;
  if (doc.tags.some((t) => t.toLowerCase().includes(kw))) score += 2;
  if (doc.key_concepts.some((c) => c.toLowerCase().includes(kw))) score += 1;
  if (doc.raw_text.toLowerCase().includes(kw)) score += 1;
  return score;
}

function buildHighlight(text: string, keyword: string, maxLen = 120): string {
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return text.slice(0, maxLen) + (text.length > maxLen ? '...' : '');
  const start = Math.max(0, idx - 30);
  const end = Math.min(text.length, idx + keyword.length + 60);
  const snippet = text.slice(start, end);
  return (start > 0 ? '...' : '') + snippet + (end < text.length ? '...' : '');
}

export const searchHandlers = [
  // 검색 상태
  http.get('/api/search/status', () => {
    return ok({
      aiAvailable: true,
      aiLive: true,
      reason: 'MSW 모크 환경에서 AI 검색이 활성화되었습니다.',
    });
  }),

  // 기본 검색
  http.get('/api/search', ({ request }) => {
    const url = new URL(request.url);
    const keyword = url.searchParams.get('keyword') ?? '';
    const category = url.searchParams.get('category') ?? '';
    const page = parseInt(url.searchParams.get('page') ?? '1');
    const size = parseInt(url.searchParams.get('size') ?? '10');

    let docs = Array.from(documentStore.values());
    if (category) docs = docs.filter((d) => d.category === category);

    const scored = docs
      .map((d) => ({ doc: d, score: scoreDoc(d, keyword) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score);

    const offset = (page - 1) * size;
    const items = scored.slice(offset, offset + size).map(({ doc, score }) => ({
      id: doc.id,
      title: doc.title,
      category: doc.category,
      summary: doc.summary,
      tags: doc.tags,
      highlight: buildHighlight(doc.raw_text || doc.summary, keyword),
      score,
    }));

    return ok({ items });
  }),

  // AI 검색 쿼리
  http.get('/api/search/query', ({ request }) => {
    const url = new URL(request.url);
    const keyword = url.searchParams.get('keyword') ?? '';
    const category = url.searchParams.get('category') ?? '';
    const size = parseInt(url.searchParams.get('size') ?? '10');
    const mode = url.searchParams.get('mode') ?? 'auto';

    let docs = Array.from(documentStore.values());
    if (category) docs = docs.filter((d) => d.category === category);

    const scored = docs
      .map((d) => ({ doc: d, score: scoreDoc(d, keyword) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, size);

    const items = scored.map(({ doc, score }) => ({
      id: doc.id,
      title: doc.title,
      category: doc.category,
      summary: doc.summary,
      tags: doc.tags,
      highlight: buildHighlight(doc.raw_text || doc.summary, keyword),
      score: mode === 'semantic' ? score * 0.95 + Math.random() * 0.05 : score,
    }));

    return ok({
      modeUsed: mode === 'auto' ? 'semantic' : mode,
      aiAvailable: true,
      items,
    });
  }),
];
