import { http, HttpResponse } from 'msw';
import { MOCK_GRAPH_NODES, MOCK_GRAPH_EDGES, MOCK_GRAPH_SUMMARY } from '../data/graph';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

function filterByCategory<T extends { category: string }>(items: T[], category?: string) {
  if (!category) return items;
  return items.filter((n) => n.category === category);
}

export const graphHandlers = [
  // GraphQL 엔드포인트
  http.post('/api/graphql', async ({ request }) => {
    const body = await request.json() as { query: string; variables?: Record<string, unknown> };
    const { query, variables = {} } = body;

    // GetNodes 쿼리
    if (query.includes('GetNodes') || (query.includes('nodes') && !query.includes('edges'))) {
      const category = variables.category as string | undefined;
      const nodes = filterByCategory(MOCK_GRAPH_NODES, category);
      return HttpResponse.json({ data: { nodes } });
    }

    // GetGraph 쿼리
    if (query.includes('GetGraph') || (query.includes('nodes') && query.includes('edges'))) {
      const category = variables.category as string | undefined;
      const nodes = filterByCategory(MOCK_GRAPH_NODES, category);
      const nodeIds = new Set(nodes.map((n) => n.id));
      const edges = category
        ? MOCK_GRAPH_EDGES.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
        : MOCK_GRAPH_EDGES;
      return HttpResponse.json({ data: { nodes, edges } });
    }

    // SearchNodes 쿼리
    if (query.includes('SearchNodes') || query.includes('searchNodes')) {
      const q = (variables.q as string ?? '').toLowerCase();
      const results = MOCK_GRAPH_NODES.filter(
        (n) =>
          n.title.toLowerCase().includes(q) ||
          n.category.toLowerCase().includes(q) ||
          n.tags.some((t) => t.toLowerCase().includes(q))
      )
        .slice(0, 10)
        .map((n) => ({
          id: n.id,
          title: n.title,
          category: n.category,
          highlight: n.title,
        }));
      return HttpResponse.json({ data: { searchNodes: results } });
    }

    return HttpResponse.json({ data: {} });
  }),

  // 그래프 요약 통계
  http.get('/api/graph/summary', () => {
    return ok(MOCK_GRAPH_SUMMARY);
  }),
];
