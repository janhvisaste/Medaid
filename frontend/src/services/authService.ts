const API_BASE_URL = (process.env.REACT_APP_API_URL || 'http://localhost:8001/api').replace(/\/+$/, '');

interface SignupData {
  email: string;
  password: string;
  confirm_password?: string;
  first_name?: string;
  last_name?: string;
  phone_number?: string;
}

interface LoginData {
  email: string;
  password: string;
}

interface AuthResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
    role?: 'patient' | 'clinician' | 'admin';
  };
}

class AuthService {
  private token: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.token = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  async signup(data: SignupData): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/signup/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await this.readErrorResponse(response, 'Signup failed');
        const errorMessage = this.errorMessage(errorData, 'Signup failed');
        throw new Error(String(errorMessage));
      }

      const result = await response.json();
      this.setTokens(result.access, result.refresh, result.user);
      return result;
    } catch (error) {
      throw this.networkError(error, 'create your account');
    }
  }

  async login(data: LoginData): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await this.readErrorResponse(response, response.statusText || 'Login failed');
        const errorMessage = this.errorMessage(errorData, response.statusText || 'Login failed');
        const err = new Error(String(errorMessage));
        (err as any).status = response.status;
        throw err;
      }

      const result = await response.json();
      this.setTokens(result.access, result.refresh, result.user);
      return result;
    } catch (error) {
      // Normalize thrown errors to be Error instances with message
      throw this.networkError(error, 'sign in');
    }
  }

  async logout(): Promise<void> {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      await fetch(`${API_BASE_URL}/auth/logout/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch (error) {
    } finally {
      this.clearTokens();
    }
  }

  private setTokens(access: string, refresh: string, user?: any): void {
    this.token = access;
    this.refreshToken = refresh;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    }
  }

  private clearTokens(): void {
    this.token = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  getUser(): any {
    const userStr = localStorage.getItem('user');
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch {
      this.clearTokens();
      return null;
    }
  }

  getToken(): string | null {
    // Always read from localStorage to get the latest token
    this.token = localStorage.getItem('access_token');
    return this.token;
  }

  isAuthenticated(): boolean {
    const access = localStorage.getItem('access_token');
    const refresh = localStorage.getItem('refresh_token');
    return Boolean(access || refresh);
  }

  getAuthHeaders(): HeadersInit {
    const token = this.getToken();
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }

  private async readErrorResponse(response: Response, fallback: string): Promise<unknown> {
    try {
      return await response.json();
    } catch {
      return response.statusText || fallback;
    }
  }

  private errorMessage(errorData: unknown, fallback: string): string {
    if (typeof errorData === 'string') return errorData;
    if (!errorData || typeof errorData !== 'object') return fallback;
    const values = Object.values(errorData as Record<string, unknown>);
    for (const value of values) {
      if (typeof value === 'string') return value;
      if (Array.isArray(value) && value.length) return String(value[0]);
    }
    return fallback;
  }

  private networkError(error: unknown, action: string): Error {
    if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
      return new Error(`Unable to reach Medaid while trying to ${action}. Check that the backend is running and try again.`);
    }
    if (error instanceof Error) return error;
    return new Error(String(error));
  }
}

const authService = new AuthService();
export default authService;
