import { http, HttpResponse } from 'msw';
import { documentStore } from './documents.handlers';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

export const calendarHandlers = [
  // 월별 캘린더
  http.get('/api/calendar', ({ request }) => {
    const url = new URL(request.url);
    const year = parseInt(url.searchParams.get('year') ?? String(new Date().getFullYear()));
    const month = parseInt(url.searchParams.get('month') ?? String(new Date().getMonth() + 1));
    const category = url.searchParams.get('category') ?? '';

    const prefix = `${year}-${String(month).padStart(2, '0')}`;
    const result: Record<string, { id: string; title: string; category: string; file_type: string }[]> = {};

    for (const doc of documentStore.values()) {
      if (!doc.capture_date) continue;
      if (!doc.capture_date.startsWith(prefix)) continue;
      if (category && doc.category !== category) continue;

      if (!result[doc.capture_date]) result[doc.capture_date] = [];
      result[doc.capture_date].push({
        id: doc.id,
        title: doc.title,
        category: doc.category,
        file_type: doc.file_type,
      });
    }

    // deadline도 캘린더에 표시
    for (const doc of documentStore.values()) {
      if (!doc.deadline) continue;
      if (!doc.deadline.startsWith(prefix)) continue;
      if (category && doc.category !== category) continue;
      if (result[doc.deadline]?.some((d) => d.id === doc.id)) continue;

      if (!result[doc.deadline]) result[doc.deadline] = [];
      result[doc.deadline].push({
        id: doc.id,
        title: `[마감] ${doc.title}`,
        category: doc.category,
        file_type: doc.file_type,
      });
    }

    return ok(result);
  }),

  // 일별 문서 목록
  http.get('/api/calendar/day', ({ request }) => {
    const url = new URL(request.url);
    const date = url.searchParams.get('date') ?? '';
    const category = url.searchParams.get('category') ?? '';

    const items = Array.from(documentStore.values())
      .filter((d) => {
        if (category && d.category !== category) return false;
        return d.capture_date === date || d.deadline === date;
      })
      .map((d) => ({
        id: d.id,
        title: d.deadline === date && d.capture_date !== date ? `[마감] ${d.title}` : d.title,
        category: d.category,
        file_type: d.file_type,
        deadline: d.deadline,
      }));

    return ok({ items });
  }),
];
