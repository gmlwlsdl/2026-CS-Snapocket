export interface MockApiNode {
  id: string;
  title: string;
  category: string;
  tags: string[];
  createdAt: string;
  connectionCount: number;
}

export interface MockApiEdge {
  source: string;
  target: string;
  weight: number;
  edgeType: 'parent_of' | 'related_to' | 'similar_to';
}

export const MOCK_GRAPH_NODES: MockApiNode[] = [
  // 강의 노드
  { id: 'doc-lec-01', title: '이산수학 - 그래프 이론 강의노트', category: 'lecture', tags: ['그래프이론', '이산수학', '알고리즘'], createdAt: '2026-03-03T10:15:00Z', connectionCount: 5 },
  { id: 'doc-lec-02', title: '자료구조 - 트리와 힙 강의노트', category: 'lecture', tags: ['트리', '자료구조', '알고리즘'], createdAt: '2026-03-10T09:30:00Z', connectionCount: 4 },
  { id: 'doc-lec-03', title: '알고리즘 - 동적 프로그래밍 강의노트', category: 'lecture', tags: ['동적프로그래밍', '알고리즘'], createdAt: '2026-03-17T11:00:00Z', connectionCount: 4 },
  { id: 'doc-lec-04', title: '운영체제 - 프로세스와 스레드', category: 'lecture', tags: ['프로세스', '스레드', '스케줄링'], createdAt: '2026-03-24T10:00:00Z', connectionCount: 3 },
  { id: 'doc-lec-05', title: '네트워크 - TCP/IP 프로토콜 스택', category: 'lecture', tags: ['TCP/IP', '네트워크'], createdAt: '2026-03-31T09:00:00Z', connectionCount: 3 },
  { id: 'doc-lec-06', title: '컴퓨터구조 - 캐시와 메모리 계층', category: 'lecture', tags: ['캐시'], createdAt: '2026-04-07T14:20:00Z', connectionCount: 2 },
  { id: 'doc-lec-07', title: '데이터베이스 - 정규화와 인덱싱', category: 'lecture', tags: ['데이터베이스', 'SQL', '정규화'], createdAt: '2026-04-14T10:30:00Z', connectionCount: 3 },
  { id: 'doc-lec-08', title: '소프트웨어공학 - 애자일과 UML', category: 'lecture', tags: ['소프트웨어공학', 'UML'], createdAt: '2026-04-21T09:00:00Z', connectionCount: 3 },
  { id: 'doc-lec-09', title: '이산수학 - 명제논리와 집합론', category: 'lecture', tags: ['이산수학'], createdAt: '2026-04-28T11:30:00Z', connectionCount: 2 },
  { id: 'doc-lec-10', title: '알고리즘 - 분할정복과 합병정렬', category: 'lecture', tags: ['분할정복', '알고리즘', '복잡도분석'], createdAt: '2026-05-06T10:00:00Z', connectionCount: 3 },
  // 과제 노드
  { id: 'doc-asgn-01', title: '[과제1] 그래프 BFS/DFS 구현', category: 'assignment', tags: ['그래프이론', '알고리즘', '과제'], createdAt: '2026-03-25T21:00:00Z', connectionCount: 3 },
  { id: 'doc-asgn-02', title: '[과제2] 이진탐색트리 구현', category: 'assignment', tags: ['트리', '자료구조', '과제'], createdAt: '2026-04-01T22:30:00Z', connectionCount: 3 },
  { id: 'doc-asgn-03', title: '[과제3] DP 최단경로 알고리즘', category: 'assignment', tags: ['동적프로그래밍', '알고리즘', '과제'], createdAt: '2026-04-08T20:00:00Z', connectionCount: 3 },
  { id: 'doc-asgn-04', title: '[과제4] 프로세스 스케줄링 시뮬레이터', category: 'assignment', tags: ['스케줄링', '프로세스', '과제'], createdAt: '2026-04-15T19:30:00Z', connectionCount: 2 },
  { id: 'doc-asgn-05', title: '[과제5] HTTP 1.1 서버 구현', category: 'assignment', tags: ['TCP/IP', '네트워크', '과제'], createdAt: '2026-04-22T21:00:00Z', connectionCount: 2 },
  { id: 'doc-asgn-06', title: '[과제6] SQL 쿼리 최적화 보고서', category: 'assignment', tags: ['데이터베이스', 'SQL', '과제'], createdAt: '2026-05-13T22:00:00Z', connectionCount: 2 },
  { id: 'doc-asgn-07', title: '[과제7] UML 클래스 다이어그램 설계', category: 'assignment', tags: ['UML', '소프트웨어공학', '과제'], createdAt: '2026-05-20T18:00:00Z', connectionCount: 2 },
  { id: 'doc-asgn-08', title: '[중간과제] 알고리즘 복잡도 분석 보고서', category: 'assignment', tags: ['알고리즘', '복잡도분석', '중간고사'], createdAt: '2026-04-25T20:00:00Z', connectionCount: 2 },
  // 공지 노드
  { id: 'doc-ntc-01', title: '2026년 1학기 이산수학 강의계획서', category: 'notice', tags: ['이산수학', '강의노트'], createdAt: '2026-03-02T08:00:00Z', connectionCount: 2 },
  { id: 'doc-ntc-02', title: '중간고사 일정 및 범위 안내', category: 'notice', tags: ['중간고사', '중요'], createdAt: '2026-04-05T09:00:00Z', connectionCount: 2 },
  { id: 'doc-ntc-03', title: '기말고사 범위 및 준비사항', category: 'notice', tags: ['기말고사', '중요'], createdAt: '2026-05-25T10:00:00Z', connectionCount: 2 },
  { id: 'doc-ntc-05', title: '팀 프로젝트 구성 및 평가기준', category: 'notice', tags: ['소프트웨어공학', 'UML'], createdAt: '2026-03-15T09:00:00Z', connectionCount: 1 },
  // 메모 노드
  { id: 'doc-mem-01', title: '중간고사 준비 노트', category: 'memo', tags: ['중간고사', '메모', '중요'], createdAt: '2026-04-10T22:00:00Z', connectionCount: 3 },
  { id: 'doc-mem-02', title: '알고리즘 Big-O 복잡도 정리', category: 'memo', tags: ['복잡도분석', '알고리즘', '메모'], createdAt: '2026-04-12T21:30:00Z', connectionCount: 3 },
  { id: 'doc-mem-03', title: '네트워크 OSI 7계층 메모', category: 'memo', tags: ['네트워크', 'TCP/IP', '메모'], createdAt: '2026-04-18T20:00:00Z', connectionCount: 2 },
  { id: 'doc-mem-05', title: '데이터베이스 핵심 개념 정리', category: 'memo', tags: ['데이터베이스', 'SQL', '메모'], createdAt: '2026-05-10T20:30:00Z', connectionCount: 2 },
];

export const MOCK_GRAPH_EDGES: MockApiEdge[] = [
  // parent_of 관계 (강의계획서 → 강의노트)
  { source: 'doc-ntc-01', target: 'doc-lec-01', weight: 0.95, edgeType: 'parent_of' },
  // parent_of 관계 (강의노트 → 과제)
  { source: 'doc-lec-01', target: 'doc-asgn-01', weight: 0.90, edgeType: 'parent_of' },
  { source: 'doc-lec-02', target: 'doc-asgn-02', weight: 0.90, edgeType: 'parent_of' },
  { source: 'doc-lec-03', target: 'doc-asgn-03', weight: 0.90, edgeType: 'parent_of' },
  { source: 'doc-lec-04', target: 'doc-asgn-04', weight: 0.88, edgeType: 'parent_of' },
  { source: 'doc-lec-05', target: 'doc-asgn-05', weight: 0.85, edgeType: 'parent_of' },
  { source: 'doc-lec-07', target: 'doc-asgn-06', weight: 0.85, edgeType: 'parent_of' },
  { source: 'doc-lec-08', target: 'doc-asgn-07', weight: 0.90, edgeType: 'parent_of' },
  // parent_of 관계 (공지 → 메모)
  { source: 'doc-ntc-02', target: 'doc-mem-01', weight: 0.80, edgeType: 'parent_of' },
  { source: 'doc-ntc-03', target: 'doc-mem-04', weight: 0.75, edgeType: 'parent_of' },
  // similar_to 관계 (같은 주제)
  { source: 'doc-lec-01', target: 'doc-lec-09', weight: 0.82, edgeType: 'similar_to' },
  { source: 'doc-lec-03', target: 'doc-lec-10', weight: 0.85, edgeType: 'similar_to' },
  { source: 'doc-lec-07', target: 'doc-mem-05', weight: 0.80, edgeType: 'similar_to' },
  { source: 'doc-asgn-08', target: 'doc-mem-02', weight: 0.88, edgeType: 'similar_to' },
  { source: 'doc-lec-05', target: 'doc-mem-03', weight: 0.82, edgeType: 'similar_to' },
  // related_to 관계 (연관 주제)
  { source: 'doc-lec-01', target: 'doc-lec-10', weight: 0.70, edgeType: 'related_to' },
  { source: 'doc-lec-02', target: 'doc-lec-03', weight: 0.72, edgeType: 'related_to' },
  { source: 'doc-lec-04', target: 'doc-lec-06', weight: 0.75, edgeType: 'related_to' },
  { source: 'doc-lec-04', target: 'doc-lec-05', weight: 0.65, edgeType: 'related_to' },
  { source: 'doc-asgn-01', target: 'doc-asgn-02', weight: 0.68, edgeType: 'related_to' },
  { source: 'doc-asgn-02', target: 'doc-asgn-03', weight: 0.65, edgeType: 'related_to' },
  { source: 'doc-mem-01', target: 'doc-mem-02', weight: 0.78, edgeType: 'related_to' },
  { source: 'doc-asgn-05', target: 'doc-mem-03', weight: 0.70, edgeType: 'related_to' },
  { source: 'doc-lec-09', target: 'doc-mem-02', weight: 0.60, edgeType: 'related_to' },
];

export const MOCK_GRAPH_SUMMARY = {
  node_count: MOCK_GRAPH_NODES.length,
  document_count: MOCK_GRAPH_NODES.length,
  documents_count: MOCK_GRAPH_NODES.length,
  tag_count: 25,
  edge_count: MOCK_GRAPH_EDGES.length,
};
