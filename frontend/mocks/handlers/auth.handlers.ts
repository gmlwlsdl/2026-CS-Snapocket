import { http, HttpResponse } from 'msw';
import { MOCK_USERS, CURRENT_USER, MOCK_TOKEN } from '../data/users';

function ok<T>(data: T, message = 'success') {
  return HttpResponse.json({ success: true, message, data });
}

export const authHandlers = [
  http.post('/api/auth/login', async ({ request }) => {
    const body = await request.json() as { email: string; password: string };
    const user = MOCK_USERS.find((u) => u.email === body.email);

    if (!user) {
      return HttpResponse.json(
        { success: false, message: '이메일 또는 비밀번호가 올바르지 않습니다.', data: null },
        { status: 401 }
      );
    }

    return ok({ access_token: MOCK_TOKEN, token_type: 'bearer' });
  }),

  http.post('/api/auth/signup', async ({ request }) => {
    const body = await request.json() as { email: string; password: string; name: string };
    const exists = MOCK_USERS.some((u) => u.email === body.email);

    if (exists) {
      return HttpResponse.json(
        { success: false, message: '이미 사용 중인 이메일입니다.', data: null },
        { status: 409 }
      );
    }

    const newId = `user-${Date.now()}`;
    return ok({ user_id: newId }, '회원가입이 완료되었습니다.');
  }),

  http.get('/api/auth/me', () => {
    return ok({
      id: CURRENT_USER.id,
      email: CURRENT_USER.email,
      name: CURRENT_USER.name,
    });
  }),

  http.post('/api/auth/logout', () => {
    return ok(null, '로그아웃 되었습니다.');
  }),
];
