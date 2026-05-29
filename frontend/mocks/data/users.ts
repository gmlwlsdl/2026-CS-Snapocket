export interface MockUser {
  id: string;
  email: string;
  name: string;
  password: string;
}

export const MOCK_USERS: MockUser[] = [
  { id: 'user-001', email: 'kim.minjun@snapocket.dev', name: '김민준', password: 'test1234' },
  { id: 'user-002', email: 'lee.seoyeon@snapocket.dev', name: '이서연', password: 'test1234' },
  { id: 'user-003', email: 'park.jiho@snapocket.dev', name: '박지호', password: 'test1234' },
  { id: 'user-004', email: 'choi.yejin@snapocket.dev', name: '최예진', password: 'test1234' },
  { id: 'user-005', email: 'jung.woosung@snapocket.dev', name: '정우성', password: 'test1234' },
];

export const CURRENT_USER = MOCK_USERS[0];
export const MOCK_TOKEN = 'mock-access-token-snapocket-dev-2026';
