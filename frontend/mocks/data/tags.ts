export interface MockTag {
  id: string;
  name: string;
  count: number;
}

export const MOCK_TAGS: MockTag[] = [
  { id: 'tag-01', name: '그래프이론', count: 5 },
  { id: 'tag-02', name: '동적프로그래밍', count: 6 },
  { id: 'tag-03', name: '트리', count: 5 },
  { id: 'tag-04', name: '알고리즘', count: 10 },
  { id: 'tag-05', name: '프로세스', count: 4 },
  { id: 'tag-06', name: '스레드', count: 3 },
  { id: 'tag-07', name: '스케줄링', count: 3 },
  { id: 'tag-08', name: 'TCP/IP', count: 3 },
  { id: 'tag-09', name: '네트워크', count: 5 },
  { id: 'tag-10', name: '캐시', count: 3 },
  { id: 'tag-11', name: '데이터베이스', count: 5 },
  { id: 'tag-12', name: 'SQL', count: 4 },
  { id: 'tag-13', name: '정규화', count: 3 },
  { id: 'tag-14', name: '소프트웨어공학', count: 3 },
  { id: 'tag-15', name: 'UML', count: 4 },
  { id: 'tag-16', name: '중간고사', count: 6 },
  { id: 'tag-17', name: '기말고사', count: 5 },
  { id: 'tag-18', name: '과제', count: 8 },
  { id: 'tag-19', name: '중요', count: 9 },
  { id: 'tag-20', name: '강의노트', count: 10 },
  { id: 'tag-21', name: '이산수학', count: 4 },
  { id: 'tag-22', name: '복잡도분석', count: 5 },
  { id: 'tag-23', name: '분할정복', count: 3 },
  { id: 'tag-24', name: '영수증', count: 5 },
  { id: 'tag-25', name: '메모', count: 5 },
];

export const MOCK_TAGS_MAP = new Map(MOCK_TAGS.map((t) => [t.id, t]));
